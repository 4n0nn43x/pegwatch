"""Reference prices (layer 2): the "real" asset, 24/7, no API key. Run every 5 min from cron.

    python -m pegwatch.ref     # one cycle -> data/ref_quotes/<day>.jsonl

Two keyless sources, joined later on `ticker` (= CMC RWA `symbol`):
- Hyperliquid HIP-3 "xyz" dex: `oraclePx` = external oracle, moves in pre/after-hours and weekends. kind="oracle".
- Ostium: `mid` with `isMarketOpen`; stocks freeze at 16:00 ET so off-session it IS the last close. kind="session"|"close".
Alpaca (all 200 tickers, extended hours) can be added as a third source when keys exist; the row shape stays the same.
"""

import sys
import time

import requests

from .collect import append

ALIAS = {"XAU": "GOLD", "XAG": "SILVER"}   # Ostium metal codes -> CMC RWA symbols


def hyperliquid() -> list[dict]:
    meta, ctxs = requests.post("https://api.hyperliquid.xyz/info", timeout=20,
                               json={"type": "metaAndAssetCtxs", "dex": "xyz"}).json()
    return [{"source": "hyperliquid", "ticker": u["name"].split(":", 1)[1], "kind": "oracle",
             "price": float(c["oraclePx"]), "prev_day": float(c["prevDayPx"]), "mark": float(c["markPx"]), "market_open": None}
            for u, c in zip(meta["universe"], ctxs) if c.get("oraclePx")]


def ostium() -> list[dict]:
    rows = requests.get("https://metadata-backend.ostium.io/PricePublish/latest-prices", timeout=20).json()
    return [{"source": "ostium", "ticker": ALIAS.get(r["from"], r["from"]), "kind": "session" if r["isMarketOpen"] else "close",
             "price": float(r["mid"]), "market_open": bool(r["isMarketOpen"]), "src_ts": int(r["timestampSeconds"])}
            for r in rows if r.get("to") == "USD" and r.get("mid")]


def cycle() -> int:
    rows, errors = [], []
    for name, fn in (("hyperliquid", hyperliquid), ("ostium", ostium)):
        try:
            rows += fn()
        except Exception as e:
            errors.append(f"{name}: {e}")
        time.sleep(0.3)
    out = append("ref_quotes", rows)
    print(f"{len(rows)} refs -> {out}" + (f" ({'; '.join(errors)})" if errors else ""))
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(cycle())
