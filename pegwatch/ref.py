"""Reference prices (layer 2): the "real" asset, 24/7, no API key. Run every 5 min from cron.

    python -m pegwatch.ref     # one cycle -> data/ref_quotes/<day>.jsonl

Two keyless sources, joined later on `ticker` (= CMC RWA `symbol`):
- Hyperliquid HIP-3 "xyz" dex: `oraclePx` = external oracle, moves in pre/after-hours and weekends. kind="oracle".
- Ostium: `mid` with `isMarketOpen`; stocks freeze at 16:00 ET so off-session it IS the last close. kind="session"|"close".
Alpaca (all 200 tickers, extended hours) can be added as a third source when keys exist; the row shape stays the same.
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from .collect import DATA, append

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


def settle(rows: list[dict], store: dict) -> list[dict]:
    """Ostium's off-session `mid` is not the last close: on 2026-09-28 it traded 229-232 during the session, then fell back
    to 225.315 (a stale close from days before) the minute the market shut. Keep the last session print per ticker in
    `store` and use it as the close while the market is shut. Mutates `store`; returns the rows to archive."""
    out = []
    for r in rows:
        if r["source"] == "ostium" and r["kind"] == "session":
            store[r["ticker"]] = {"price": r["price"], "src_ts": r["src_ts"]}
        elif r["source"] == "ostium" and r["kind"] == "close" and r["ticker"] in store:
            r = {**r, "price": store[r["ticker"]]["price"], "stale_mid": r["price"], "close_src_ts": store[r["ticker"]]["src_ts"]}
        out.append(r)
    return out


def seed(days: int = 4) -> dict:
    """Last session print per ticker from the recent archive: rebuilds the store after a deploy or a lost cache."""
    store = {}
    today = datetime.now(timezone.utc).date()
    for d in sorted(today - timedelta(n) for n in range(days)):
        f = DATA / "ref_quotes" / f"{d}.jsonl"
        if not f.exists():
            continue
        for line in f.open():
            r = json.loads(line)
            if r.get("source") == "ostium" and r.get("kind") == "session":
                store[r["ticker"]] = {"price": r["price"], "src_ts": r["src_ts"]}
    return store


def cycle() -> int:
    rows, errors = [], []
    for name, fn in (("hyperliquid", hyperliquid), ("ostium", ostium)):
        try:
            rows += fn()
        except Exception as e:
            errors.append(f"{name}: {e}")
        time.sleep(0.3)
    path = DATA / "cache" / "last_session.json"
    store = json.loads(path.read_text()) if path.exists() else seed()
    rows = settle(rows, store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store))
    out = append("ref_quotes", rows)
    print(f"{len(rows)} refs -> {out}" + (f" ({'; '.join(errors)})" if errors else ""))
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(cycle())
