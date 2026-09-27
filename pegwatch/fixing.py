"""Layer 1 fixing: depth-weighted median USDT price per fiat and rail vs the official rate.

    python -m pegwatch.fixing          # latest P2P snapshot -> data/fixing/latest.json (+ sha256), prints a table
    python -m pegwatch.fixing --daily  # also archives data/fixing/<day>.json: the signed 12:00 UTC fixing
    python -m pegwatch.fixing XOF      # one fiat, printed only

Every 5 min for the live ladder; once a day with --daily for the archive.
Pure logic (weighted_median, rail_of, fixing) has no I/O and is tested in tests/test_fixing.py.
"""

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

from .collect import DATA, latest, usdt_in_fiats

MIN_USD = 100          # ads that cannot fill 100 $ are bait or dust, ignored
MAX_W = 2.0            # weight cap per ad = MAX_W x the bucket's median depth: a few huge fake ads cannot outweigh the real market
EUR_PEG = 655.957      # XOF and XAF are fixed to EUR, the USD rate floats with EUR/USD
THIN_USD = 20_000      # a buy side with less depth than this (or under 10 ads) is flagged thin
NO_P2P = ["EUR"]        # fiats of countries without a P2P layer (countries.yaml rails: []): they still need an official rate
CROSSED = 0.98         # buy median below 98 % of the sell median = the buy ads are not fillable, the sell side is the real price

# Central-bank official rates where open.er-api.com is stale, blended or lagging (research of 2026-09-16, see FEEDBACK.md and the vault).
# A constant carries the date it was checked; a URL is fetched each run and falls back to er-api on failure.
OFFICIAL = {
    "VES": ("https://ve.dolarapi.com/v1/dolares/oficial", "promedio", "BCV via ve.dolarapi.com"),
    "ARS": ("https://dolarapi.com/v1/dolares/oficial", "venta", "BCRA minorista via dolarapi.com"),
    "BOB": ("https://bo.dolarapi.com/v1/dolares/oficial", "venta", "BCB tipo de cambio oficial via bo.dolarapi.com"),
    "IQD": (1310.0, None, "CBI fixed rate 1310 (checked 2026-09-16)"),
    "LBP": (89500.0, None, "BdL unified rate 89 500 (checked 2026-09-16)"),
    "SDG": (600.0, None, "CBOS ~600 per USD, banks set own rates since circular 16/2026 (er-api is frozen at 2022; checked 2026-09-16)"),
    "AOA": ("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json", "usd.aoa", "BNA reference via fawazahmed0 currency-api (bna.ao has no stable API)"),
}

# ponytail: substring rules, first match wins. Extend when a new mobile-money label shows up in data.
# A third element restricts the rule to those fiats: BBVA, Santander or Banco Popular exist in many countries and
# are only "Mexican bank" / "Dominican bank" in MXN / DOP; elsewhere they fall through to the generic "Bank".
RAILS = [
    (r"momo|zalo", "MoMo", {"VND"}),        # the Vietnamese wallet, not MTN
    (r"wave", "Wave"), (r"mtn|momo", "MTN MoMo"), (r"moov", "Moov Money"), (r"orange", "Orange Money"),
    (r"airtel|atmoney", "Airtel Money"), (r"t-?money", "T-Money"), (r"m-?pesa", "M-Pesa"),
    (r"vodafone|telecel", "Telecel Cash"), (r"\bopay|paycom", "OPay"), (r"palm ?pay", "PalmPay"),
    (r"neopay|qi ?serv|zain ?cash|\bfib\b", "Iraqi wallet", {"IQD"}), (r"nayapay|sadapay", "Pakistani wallet", {"PKR"}),
    (r"pumb|sense|privat|monobank", "Ukrainian bank", {"UAH"}),
    (r"ziraat|garanti|kuveyt|akbank|vakif|isbank|yapi", "Turkish bank", {"TRY"}), (r"baridimob|\bccp\b", "BaridiMob", {"DZD"}),
    (r"bre-b|llaves", "Bre-B", {"COP"}),
    (r"\bstp\b|bbva|banorte|santander|banamex", "Mexican bank", {"MXN"}), (r"banreservas|popular", "Dominican bank", {"DOP"}),
    (r"kuda", "Kuda"), (r"moniepoint", "Moniepoint"), (r"instapay", "InstaPay"),
    (r"pix", "Pix"), (r"mercado ?pago", "Mercado Pago"), (r"nequi", "Nequi"), (r"yape", "Yape"), (r"plin", "Plin"), (r"daviplata", "Daviplata"),
    (r"pago ?m[oó]vil", "Pago Móvil"), (r"spei|oxxo", "SPEI"), (r"papara", "Papara"), (r"jazz ?cash", "JazzCash"), (r"easypaisa", "Easypaisa"),
    (r"bkash", "bKash"), (r"nagad", "Nagad"), (r"upi", "UPI"), (r"gcash", "GCash"), (r"maya|paymaya", "Maya"),
    (r"\b(dana|ovo|gopay)\b", "e-wallet", {"IDR"}),   # word-bounded: "Novo Banco" is not OVO
    (r"kaspi", "Kaspi"), (r"esewa|khalti", "eSewa"), (r"telebirr", "Telebirr"),
    (r"wise|revolut|zelle|paypal|skrill|payoneer|advcash", "Fintech"), (r"cash|efectivo", "Cash"), (r"bank|transfer|banco|sepa|iban", "Bank"),
]


def rail_of(pay: str, fiat: str = "") -> str:
    for pat, rail, *only in RAILS:
        if only and fiat not in only[0]:
            continue
        if re.search(pat, pay, re.I):
            return rail
    return "Other"


def weighted_median(pairs: list[tuple[float, float]]) -> float:
    """Median of prices weighted by depth: the price at which half the depth is cheaper."""
    pairs = sorted(p for p in pairs if p[1] > 0)
    total, acc = sum(w for _, w in pairs), 0.0
    for price, w in pairs:
        acc += w
        if acc >= total / 2:
            return price
    raise ValueError("no depth")


def fixing(rows: list[dict], min_usd: float = MIN_USD) -> dict:
    """{fiat: {side: {rail: {price, n, depth_usd}}}}, rail "ALL" = every ad of that side."""
    buckets: dict[tuple, list] = defaultdict(list)
    for r in rows:
        depth_usd = r["max_fiat"] / r["price"]
        if depth_usd < min_usd:
            continue
        for rail in {rail_of(p, r["fiat"]) for p in r["pay"]} | {"ALL"}:
            buckets[(r["fiat"], r["side"], rail)].append((r["price"], depth_usd))
    out: dict = defaultdict(lambda: defaultdict(dict))
    for (fiat, side, rail), pairs in buckets.items():
        cap = MAX_W * sorted(w for _, w in pairs)[len(pairs) // 2]
        out[fiat][side][rail] = {"price": weighted_median([(p, min(w, cap)) for p, w in pairs]), "n": len(pairs), "depth_usd": round(sum(w for _, w in pairs))}
    return {f: {s: dict(v) for s, v in sides.items()} for f, sides in out.items()}


def headline(sides: dict, official: float) -> dict:
    """The one number for a fiat: the cost of a dollar. Buy side unless the book is crossed (fake buy ads), thin flagged."""
    buy, sell = sides.get("buy", {}).get("ALL"), sides.get("sell", {}).get("ALL")
    if not buy and not sell:
        return {}
    crossed = bool(buy and sell and buy["price"] < sell["price"] * CROSSED)
    ref = sell if crossed or not buy else buy
    h = {"price": ref["price"], "premium_pct": round(ref["price"] / official - 1, 4), "crossed": crossed,
         "thin": bool(buy is None or buy["depth_usd"] < THIN_USD or buy["n"] < 10),
         "sell_premium_pct": round(sell["price"] / official - 1, 4) if sell else None}
    sides["dollar"] = h
    return h


def vs_cmc(h: dict, cmc_price: float | None, official: float) -> None:
    """Add the third leg to a headline: CMC's aggregated USDT price in that fiat, and the P2P dollar against it.
    CMC tracks the exchange-traded rate, so P2P vs CMC isolates what the street charges on top of the market."""
    if h and cmc_price:
        h["cmc_price"] = round(cmc_price, 6)
        h["vs_cmc_pct"] = round(h["price"] / cmc_price - 1, 4)
        h["cmc_vs_official_pct"] = round(cmc_price / official - 1, 4)


def official_rates(fiats: list[str]) -> dict:
    """USD -> fiat official rate. XOF/XAF via the EUR peg, central-bank overrides from OFFICIAL, open.er-api.com blend otherwise."""
    rates = requests.get("https://open.er-api.com/v6/latest/USD", timeout=20).json()["rates"]
    out = {}
    for f in fiats:
        if f in ("XOF", "XAF"):
            out[f] = {"rate": EUR_PEG * rates["EUR"], "source": "BCEAO/BEAC peg 655.957 XOF per EUR, EUR/USD from open.er-api.com"}
        elif f in OFFICIAL:
            src, field, label = OFFICIAL[f]
            try:
                if isinstance(src, str):
                    v = requests.get(src, timeout=15).json()
                    for k in field.split("."):
                        v = v[k]
                    src = float(v)
                out[f] = {"rate": float(src), "source": label}
            except Exception as e:
                out[f] = {"rate": rates[f], "source": f"open.er-api.com blend (fallback, {label} failed: {e})"}
        else:
            out[f] = {"rate": rates[f], "source": "open.er-api.com blended reference"}
    return out


def latest_snapshot(fiats: list[str] | None = None) -> tuple[str, list[dict]]:
    ts, rows = latest("p2p")
    return ts, [r for r in rows if not fiats or r["fiat"] in fiats]


def build(fiats: list[str] | None = None) -> dict:
    ts, rows = latest_snapshot(fiats)
    fx = fixing(rows)
    off = official_rates(sorted(set(fx) | set(NO_P2P)))
    try:
        cmc = usdt_in_fiats()
    except Exception as e:                    # the fixing never waits on CMC: without it the third leg is just missing
        cmc = {"ts": None, "prices": {}, "error": str(e)}
    for fiat, sides in fx.items():
        for rails in sides.values():
            for v in rails.values():
                v["premium_pct"] = round(v["price"] / off[fiat]["rate"] - 1, 4)
        vs_cmc(headline(sides, off[fiat]["rate"]), cmc["prices"].get(fiat), off[fiat]["rate"])
    cmc_doc = {"ts": cmc["ts"], "source": "CMC /v2/cryptocurrency/quotes/latest, USDT (id 825) converted to each fiat in /v1/fiat/map",
               "prices": {f: p for f, p in cmc["prices"].items() if f in fx}, **({"error": cmc["error"]} if "error" in cmc else {})}
    doc = {"ts": ts, "min_usd": MIN_USD, "official": off, "fixing": fx, "cmc_usdt": cmc_doc,
           "method": "premium = depth-weighted median ask for USDT on Binance, Bybit and OKX P2P / central-bank official rate - 1 "
                     "(BIS/IMF parity deviation, Aldasoro, Beltran & Grinberg 2026; IMF parallel premium, Tan 2026)"}
    doc["sha256"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    return doc


def main(argv: list[str]) -> int:
    daily, fiats = "--daily" in argv, [a for a in argv if not a.startswith("--")]
    doc = build(fiats or None)
    if not doc["fixing"]:
        print("no P2P data yet"); return 0
    out = DATA / "fixing" / ("latest.json" if not fiats else "_preview.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True)
    out.write_text(text)
    if daily:
        (out.parent / f"{doc['ts'][:10]}.json").write_text(text)
    print(f"fixing {doc['ts']}  sha256 {doc['sha256'][:16]}  -> {out}" + (" (+ daily archive)" if daily else ""))
    for fiat, sides in sorted(doc["fixing"].items()):
        o = doc["official"][fiat]["rate"]
        print(f"\n{fiat}  official {o:.2f}")
        for side in ("buy", "sell"):
            for rail, v in sorted(sides.get(side, {}).items(), key=lambda kv: -kv[1]["depth_usd"]):
                print(f"  {side:4} {rail:13} {v['price']:>9.2f}  {v['premium_pct']*100:+5.1f}%  n={v['n']:<3} depth={v['depth_usd']:,} $")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
