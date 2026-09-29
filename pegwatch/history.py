"""Layer 2 over time: 30 daily closes of every wrapper against the 24/7 perp price CoinMarketCap lists for the same asset.

CMC has no history endpoint for real-world assets, but every wrapper and the "<TICKER> (Derivatives)" pseudo-token carry a
crypto_id, and /v2/cryptocurrency/ohlcv/historical returns their daily closes (1 credit per 100 points). The perp
aggregate trades 24/7, so it is the same kind of reference pegwatch uses on weekends. Run daily.

    python -m pegwatch.history      -> data/history/<SYMBOL>.json + data/history/index.json
"""

import json
import sys
from datetime import datetime, timezone

from .collect import DATA, get, latest
from .premiums import PERP_ISSUERS, UNIT

DAYS = 30
BATCH = 100          # ids per call: 100 x 30 daily points = 30 credits


def daily_closes(ohlcv: dict) -> dict[str, float]:
    """{YYYY-MM-DD: close} from one id's ohlcv/historical payload."""
    return {q["time_close"][:10]: q["quote"]["USD"]["close"] for q in ohlcv.get("quotes") or [] if q["quote"]["USD"].get("close")}


def premium_series(ref: dict[str, float], wrapper: dict[str, float], unit: float = 1.0) -> dict[str, float]:
    """Daily premium of a wrapper against the reference, on the days both have a close."""
    return {d: round(wrapper[d] * unit / ref[d] - 1, 5) for d in sorted(ref) if d in wrapper and ref[d]}


def summary(series: dict[str, float]) -> dict:
    """Mean, range, last value and where the last value sits among the 30 days (0 = cheapest day, 100 = richest)."""
    xs = list(series.values())
    if not xs:
        return {}
    last = xs[-1]
    return {"days": len(xs), "mean_pct": round(sum(xs) / len(xs), 5), "min_pct": min(xs), "max_pct": max(xs), "last_pct": last,
            "last_percentile": round(100 * sum(x <= last for x in xs) / len(xs))}


def plan(assets: list[dict], priced: dict[str, dict]) -> list[dict]:
    """Assets worth a history: a perp reference token and at least one tradable wrapper (not a perp, not suspect)."""
    jobs = []
    for a in assets:
        p = priced.get(a["symbol"])
        if not p:
            continue
        ok = {(t["symbol"], t["issuer"]) for t in p["tokens"] if not t["is_perp"] and not t["suspect"]}
        toks = [t for t in a.get("tokens") or [] if t.get("crypto_id")]
        ref = next((t for t in toks if t.get("issuer_name") == "NA (Derivatives)"), None)
        wrappers = [t for t in toks if (t["symbol"], t.get("issuer_name")) in ok and t.get("issuer_name") not in PERP_ISSUERS]
        if ref and wrappers:
            jobs.append({"symbol": a["symbol"], "name": a["name"], "ref": ref, "wrappers": wrappers})
    return jobs


def main() -> int:
    _, assets = latest("rwa_quotes")
    prem = DATA / "premiums" / "latest.json"
    if not assets or not prem.exists():
        print("waiting for rwa_quotes and premiums"); return 0
    jobs = plan(assets, {a["symbol"]: a for a in json.loads(prem.read_text())["assets"]})
    ids = sorted({t["crypto_id"] for j in jobs for t in [j["ref"], *j["wrappers"]]})
    closes: dict[int, dict[str, float]] = {}
    for i in range(0, len(ids), BATCH):
        body = get("/v2/cryptocurrency/ohlcv/historical", id=",".join(map(str, ids[i:i + BATCH])),
                   time_period="daily", interval="daily", count=DAYS)
        for k, v in body["data"].items():
            closes[int(k)] = daily_closes(v)
    out = DATA / "history"
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index = []
    for j in jobs:
        ref = closes.get(j["ref"]["crypto_id"], {})
        rows = []
        for t in j["wrappers"]:
            s = premium_series(ref, closes.get(t["crypto_id"], {}), UNIT.get(t["symbol"], 1))
            if s:
                rows.append({"symbol": t["symbol"], "issuer": t["issuer_name"], "series": s, **summary(s)})
        if not rows:
            continue
        doc = {"asset": j["symbol"], "name": j["name"], "ts": now, "reference": "24/7 perp aggregate price, daily close",
               "days": sorted(ref), "wrappers": sorted(rows, key=lambda r: r["symbol"])}
        (out / f"{j['symbol']}.json").write_text(json.dumps(doc, indent=1))
        index.append({"asset": j["symbol"], "wrappers": len(rows)})
    (out / "index.json").write_text(json.dumps({"ts": now, "assets": index}, indent=1))
    print(f"{len(index)} assets, {len(ids)} ids -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
