"""Layer 2: premium of every tokenized wrapper vs the real asset, per trading regime. Run every 5 min after collect + ref.

    python -m pegwatch.premiums    # latest rwa_quotes x latest ref_quotes -> data/premiums/latest.json (+ <day>.jsonl history)

Reference rule (premium.pick_reference): session print during the session, oracle in pre/after-hours, last close
at night / weekend / holiday. Off-session the Hyperliquid oracle is also reported as `proxy` (what the perps think).
"""

import json
import sys
from datetime import datetime, timezone

from .collect import DATA, append, latest
from .premium import RefQuote, premium, wrapper_spread

PERP_ISSUERS = {"NA (Derivatives)", "Hyperliquid Assets"}   # perp prices listed as tokens by CMC, not spot wrappers
OZ = 31.1034768                     # grams per troy ounce
UNIT = {"CGO": OZ, "VNXAU": OZ, "GRAMS": OZ}   # tokens quoted per gram while the reference is per ounce
SUSPECT = 0.20                      # |premium| beyond this is a unit or data problem, not a market signal


def compute(assets: list[dict], refs: list[dict], ts: datetime) -> list[dict]:
    """One entry per asset that has a reference; tokens without a price are skipped."""
    ost = {r["ticker"]: r for r in refs if r["source"] == "ostium"}
    hl = {r["ticker"]: r for r in refs if r["source"] == "hyperliquid"}
    out = []
    for a in assets:
        o, h = ost.get(a["symbol"]), hl.get(a["symbol"])
        if not o and not h:
            continue
        close = o["price"] if o else h["price"]
        q = RefQuote(last_close=close, extended=h["price"] if h else None,
                     session=o["price"] if o and o["kind"] == "session" else None)
        tokens, prices = [], {}
        for t in a.get("tokens") or []:
            if not t.get("price"):
                continue
            price = t["price"] * UNIT.get(t["symbol"], 1)
            p = premium(price, q, ts)
            row = {"symbol": t["symbol"], "issuer": t["issuer_name"], "price": price, "premium_pct": round(p.premium_pct, 5),
                   "vs_proxy_pct": round(price / h["price"] - 1, 5) if h else None, "volume_24h": t.get("volume_24h"),
                   "is_perp": t["issuer_name"] in PERP_ISSUERS,
                   "suspect": abs(p.premium_pct) > SUSPECT or not t.get("volume_24h")}   # unit problem or no market
            tokens.append(row)
            if not row["is_perp"] and not row["suspect"]:
                prices[t["symbol"]] = price
        if not tokens:
            continue
        out.append({"rwa_id": a["rwa_id"], "symbol": a["symbol"], "name": a["name"], "asset_type": a["asset_type"],
                    "regime": p.regime, "ref_price": p.ref_price, "ref_session": p.ref_session,
                    "proxy": h["price"] if h else None, "wrapper_spread_pct": round(wrapper_spread(prices), 5),
                    "tokens": sorted(tokens, key=lambda t: -(t["volume_24h"] or 0))})
    return out


def main() -> int:
    ts_a, assets = latest("rwa_quotes")
    ts_r, refs = latest("ref_quotes")
    if not assets or not refs:
        print("waiting for rwa_quotes and ref_quotes"); return 0
    now = datetime.now(timezone.utc)
    rows = compute(assets, refs, now)
    out = DATA / "premiums" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "rwa_ts": ts_a, "ref_ts": ts_r, "assets": rows}, indent=1))
    append("premiums", [{"asset": r["symbol"], "regime": r["regime"], "ref_price": r["ref_price"], "ref_session": r["ref_session"],
                         "proxy": r["proxy"], **t} for r in rows for t in r["tokens"]])
    print(f"{len(rows)} assets, {sum(len(r['tokens']) for r in rows)} tokens, regime={rows[0]['regime'] if rows else '-'} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
