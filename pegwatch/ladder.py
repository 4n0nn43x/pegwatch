"""The ladder: what it really costs to own a tokenized asset from a given country, right now.

    python -m pegwatch.ladder             # every country -> data/ladder/<CC>.json
    python -m pegwatch.ladder BJ NVDA 300000   # print one ladder

Joins the three layers: fixing (dollar premium per rail), wrappers.yaml (who may buy what), premiums (wrapper premium
vs the real asset). total = (1 + dollar premium) * (1 + wrapper premium) - 1. Information only, no execution.
"""

import json
import sys
from pathlib import Path

import yaml

from .collect import DATA, rwa_issuers
from .premiums import PERP_ISSUERS

ROOT = Path(__file__).resolve().parent.parent
STATUS_ORDER = {"allowed": 0, "likely": 1, "unclear": 2, "excluded": 3}


def load_static() -> tuple[dict, dict]:
    wrappers = {w["issuer_name"]: w for w in yaml.safe_load((ROOT / "wrappers.yaml").read_text())}
    countries = yaml.safe_load((ROOT / "countries.yaml").read_text())
    return wrappers, countries


def access(w: dict | None, cc: str) -> str:
    """allowed / excluded / unclear come from the verified lists in wrappers.yaml (11 countries). Any other country:
    "likely" when the issuer publishes an exclusion list it is not on, "unclear" when the issuer publishes nothing."""
    if not w:
        return "unclear"                     # issuer not in wrappers.yaml (small ones): say so, never guess
    if cc in w["allowed"]:
        return "allowed"
    if cc in w["excluded"]:
        return "excluded"
    if cc in w["unclear"] or not w["allowed"]:
        return "unclear"
    return w.get("default", "likely")


def dollar(cc: str, country: dict, fixing: dict) -> dict:
    """Layer 1 for one country: official rate and the buy-side premium on each local rail."""
    fiat = country["fiat"]
    off = 1.0 if fiat == "USD" else fixing.get("official", {}).get(fiat, {}).get("rate")
    if country.get("rails") == []:            # no P2P layer (FR, US): the dollar is bought at the official rate
        return {"fiat": fiat, "official": off, "p2p": False, "rails": [], "best": None, "premium_pct": 0.0}
    if fiat not in fixing.get("fixing", {}):  # P2P country missing from this fixing: no rate at all, never a silent 1:1
        return {"fiat": fiat, "official": None, "p2p": True, "rails": [], "best": None, "premium_pct": None}
    buy = fixing["fixing"][fiat].get("buy", {})
    wanted = country.get("rails") or sorted((r for r in buy if r not in ("ALL", "Other")), key=lambda r: -buy[r]["depth_usd"])
    rails = [{"rail": r, **buy[r]} for r in wanted if r in buy]
    rails.sort(key=lambda r: r["price"])
    head = fixing["fixing"][fiat].get("dollar", {})
    best = rails[0] if rails else {"rail": "ALL", **buy["ALL"]} if "ALL" in buy else None
    if head.get("crossed") or not best:        # buy ads are not fillable (or absent): the sell side is what a dollar really costs
        label = "market (crossed book)" if head.get("crossed") else "market (sell side)" if head else None
        return {"fiat": fiat, "official": off, "p2p": True, "rails": rails, "best": label,
                "premium_pct": head.get("premium_pct"), "crossed": bool(head.get("crossed")), "thin": bool(head.get("thin"))}
    return {"fiat": fiat, "official": off, "p2p": True, "rails": rails, "best": best["rail"],
            "premium_pct": best["premium_pct"], "crossed": False, "thin": bool(head.get("thin"))}


def ladder(cc: str, country: dict, fixing: dict, premiums: dict, wrappers: dict) -> dict:
    usd = dollar(cc, country, fixing)
    assets = []
    for a in premiums["assets"]:
        rows = []
        for t in a["tokens"]:
            if t["is_perp"] or t["suspect"]:
                continue
            st = access(wrappers.get(t["issuer"]), cc)
            w = wrappers.get(t["issuer"], {})
            rows.append({"symbol": t["symbol"], "issuer": t["issuer"], "price": t["price"], "premium_pct": t["premium_pct"],
                         "access": st, "kyc": w.get("kyc"), "redemption": w.get("redemption"),
                         "total_pct": round((1 + usd["premium_pct"]) * (1 + t["premium_pct"]) - 1, 5)
                         if st != "excluded" and usd["premium_pct"] is not None else None})
        rows.sort(key=lambda r: (STATUS_ORDER[r["access"]], r["total_pct"] if r["total_pct"] is not None else 9))
        best = next((r for r in rows if r["access"] in ("allowed", "likely")), None)
        assets.append({"symbol": a["symbol"], "name": a["name"], "asset_type": a["asset_type"], "regime": a["regime"],
                       "ref_price": a["ref_price"], "ref_session": a["ref_session"], "proxy": a["proxy"],
                       "best": best["symbol"] if best else None, "best_total_pct": best["total_pct"] if best else None,
                       "wrappers": rows})
    return {"country": cc, "name": country["name"], "fiat": country["fiat"], "lat": country.get("lat"), "lon": country.get("lon"),
            "ts": premiums["ts"], "fixing_ts": fixing.get("ts"), "dollar": usd, "assets": assets}


def true_price(cc: str, asset: str, amount_fiat: float, lad: dict) -> dict:
    """One asset from one country for one amount: the answer an agent or a person wants."""
    a = next((x for x in lad["assets"] if x["symbol"] == asset), None)
    if not a:
        raise KeyError(f"no reference for {asset}")
    usd = lad["dollar"]
    if not usd["official"] or usd["premium_pct"] is None:
        raise ValueError(f"no {usd['fiat']} rate in the current fixing for {lad['country']}, cannot convert the amount")
    usd_amount = amount_fiat / (usd["official"] * (1 + usd["premium_pct"]))
    return {**{k: lad[k] for k in ("country", "name", "ts")}, "asset": asset, "amount_fiat": amount_fiat, "fiat": usd["fiat"],
            "dollar": {"official": usd["official"], "best_rail": usd["best"], "premium_pct": usd["premium_pct"], "usd": round(usd_amount, 2)},
            "reference": {"price": a["ref_price"], "session": a["ref_session"], "regime": a["regime"], "proxy": a["proxy"]},
            "wrappers": [{**w, "units": round(usd_amount / w["price"], 4) if w["access"] != "excluded" else None} for w in a["wrappers"]],
            "best": a["best"], "best_total_pct": a["best_total_pct"]}


def coverage(cmc_issuers: list[dict], wrappers: dict) -> dict:
    """How much of CMC's RWA catalogue the hand-checked access matrix covers, by issuer and by token count. Perps are
    not wrappers anyone buys from an issuer, they are left out of the denominator."""
    rows = [{"issuer": i["name"], "website": i["website"], "tokens": i["num_tokens"], "access_verified": i["name"] in wrappers}
            for i in cmc_issuers if i["name"] not in PERP_ISSUERS and i["num_tokens"]]
    total = sum(r["tokens"] for r in rows)
    return {"issuers": sorted(rows, key=lambda r: -r["tokens"]),
            "verified_issuers": sum(r["access_verified"] for r in rows), "listed_issuers": len(rows),
            "verified_token_share": round(sum(r["tokens"] for r in rows if r["access_verified"]) / total, 4) if total else None}


def main(argv: list[str]) -> int:
    wrappers, countries = load_static()
    fx_path, pr_path = DATA / "fixing" / "latest.json", DATA / "premiums" / "latest.json"
    if not pr_path.exists():
        print("waiting for premiums"); return 0
    fixing = json.loads(fx_path.read_text()) if fx_path.exists() else {}
    premiums = json.loads(pr_path.read_text())
    if argv:
        cc, asset, amount = argv[0], argv[1], float(argv[2]) if len(argv) > 2 else 100.0
        print(json.dumps(true_price(cc, asset, amount, ladder(cc, countries[cc], fixing, premiums, wrappers)), indent=1, ensure_ascii=False))
        return 0
    out = DATA / "ladder"
    out.mkdir(parents=True, exist_ok=True)
    world = []
    for cc, c in countries.items():
        lad = ladder(cc, c, fixing, premiums, wrappers)
        (out / f"{cc}.json").write_text(json.dumps(lad, ensure_ascii=False))
        sell = fixing.get("fixing", {}).get(c["fiat"], {}).get("sell", {}).get("ALL")
        nvda = next((a for a in lad["assets"] if a["symbol"] == "NVDA"), None)
        world.append({"cc": cc, "name": c["name"], "fiat": c["fiat"], "lat": c.get("lat"), "lon": c.get("lon"),
                      "official": lad["dollar"]["official"], "premium_pct": lad["dollar"]["premium_pct"],
                      "sell_premium_pct": sell["premium_pct"] if sell else None, "best_rail": lad["dollar"]["best"],
                      "crossed": lad["dollar"].get("crossed", False), "thin": lad["dollar"].get("thin", False),
                      "rails": [r["rail"] for r in lad["dollar"]["rails"][:4]],
                      "wrappers_ok": sum(1 for w in (nvda["wrappers"] if nvda else []) if w["access"] in ("allowed", "likely")),
                      "nvda_total_pct": nvda["best_total_pct"] if nvda else None})
    try:
        cov = coverage(rwa_issuers()["issuers"], wrappers)
    except Exception as e:                   # CMC down or no key: the ladders still ship, the coverage line says why
        cov = {"error": str(e)}
    (DATA / "world.json").write_text(json.dumps({"ts": premiums["ts"], "fixing_ts": fixing.get("ts"), "countries": world,
                                                 "access_coverage": cov}, ensure_ascii=False))
    print(f"{len(countries)} ladders + world.json -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
