"""Monday scoreboard: who priced the weekend right? Run Monday after the open (and any time for the archive).

    python -m pegwatch.monday    # every weekend on disk -> data/monday/latest.json, prints the table

For each weekend and each asset: the last price of every wrapper while the reference was frozen (Sunday night for
stocks, Sunday before 18:00 ET for metals) vs the first real print after the weekend (Ostium session). The error of a
wrapper is sunday_price / monday_open - 1; the perp oracle (Hyperliquid, `proxy`) competes as "perps"; holding Friday's
close is the naive baseline. Tests CMC Research's peg-tightness ranking bStocks > xStocks > Ondo with real weekends.
Pure logic (score) has no I/O and is tested in tests/test_monday.py.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

from .collect import DATA, db

NY = "America/New_York"
PERPS = "perps"          # the proxy competes under this issuer name


def snapshots() -> list[dict]:
    """One row per (weekend, wrapper): last weekend snapshot before the reference reopened, joined with the open print."""
    pf, rf = str(DATA / "premiums" / "*.jsonl"), str(DATA / "ref_quotes" / "*.jsonl")
    if not list((DATA / "premiums").glob("*.jsonl")) or not list((DATA / "ref_quotes").glob("*.jsonl")):
        return []
    rel = db().sql(f"""
        with p as (select *, ts::timestamptz at time zone '{NY}' as ny from read_json_auto('{pf}', union_by_name=true) where regime = 'weekend'),
        r as (select ts, ticker, price, ts::timestamptz at time zone '{NY}' as ny from read_json_auto('{rf}', union_by_name=true)
              where source = 'ostium' and kind = 'session'),
        reopen as (
            select ticker, mon, min(ts) as reopen, arg_min(price, ts) as open_price from (
                select ticker, ts, price, dayofweek(ny) as dow,
                       case when dayofweek(ny) = 0 then date_trunc('week', ny::date) + interval 7 day
                            else date_trunc('week', ny::date) end as mon
                from r) where dow in (0, 1) group by ticker, mon)
        select p.asset, strftime(rp.mon, '%Y-%m-%d') as monday, p.symbol, p.issuer, p.price, p.proxy, p.ref_price,
               rp.open_price, p.is_perp, coalesce(p.suspect, false) as suspect,
               strftime(p.ts, '%Y-%m-%dT%H:%M:%SZ') as sunday_ts,
               strftime(rp.reopen, '%Y-%m-%dT%H:%M:%SZ') as open_ts
        from p join reopen rp on rp.ticker = p.asset and rp.mon = date_trunc('week', p.ny::date) + interval 7 day
        where p.ts < rp.reopen
        qualify p.ts = max(p.ts) over (partition by p.symbol, rp.mon)
        order by monday, p.asset, p.symbol""")
    return [dict(zip(rel.columns, r)) for r in rel.fetchall()]


def score(rows: list[dict]) -> dict:
    """{"weekends": [...per Monday...], "cumulative": [...per issuer...]} from snapshot rows."""
    by_wk: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if not r["is_perp"] and not r["suspect"] and r["price"] and r["open_price"]:
            by_wk[r["monday"]][r["asset"]].append(r)
    weekends, cum = [], defaultdict(lambda: {"n": 0, "abs_err": 0.0, "wins": 0, "beat_close": 0})
    for monday, assets in sorted(by_wk.items()):
        wk_assets, wk_iss = [], defaultdict(lambda: {"n": 0, "abs_err": 0.0, "wins": 0, "beat_close": 0})
        for asset, toks in sorted(assets.items()):
            head = toks[0]
            open_, close = head["open_price"], head["ref_price"]
            naive = abs(close / open_ - 1)
            entries = [{"symbol": t["symbol"], "issuer": t["issuer"], "sunday_price": t["price"],
                        "err_pct": round(t["price"] / open_ - 1, 5)} for t in toks]
            if head.get("proxy"):
                entries.append({"symbol": "oracle", "issuer": PERPS, "sunday_price": head["proxy"], "err_pct": round(head["proxy"] / open_ - 1, 5)})
            for e in entries:
                e["beat_close"] = abs(e["err_pct"]) < naive
            winner = min(entries, key=lambda e: abs(e["err_pct"]))
            for e in entries:
                for agg in (wk_iss[e["issuer"]], cum[e["issuer"]]):
                    agg["n"] += 1; agg["abs_err"] += abs(e["err_pct"]); agg["beat_close"] += e["beat_close"]; agg["wins"] += e is winner
            wk_assets.append({"asset": asset, "friday_close": close, "monday_open": open_, "gap_pct": round(open_ / close - 1, 5),
                              "sunday_ts": head["sunday_ts"], "open_ts": head["open_ts"], "winner": winner["issuer"],
                              "tokens": sorted(entries, key=lambda e: abs(e["err_pct"]))})
        weekends.append({"monday": monday, "assets": wk_assets, "issuers": _table(wk_iss)})
    return {"weekends": weekends, "cumulative": _table(cum)}


def _table(agg: dict) -> list[dict]:
    rows = [{"issuer": k, "n": v["n"], "mae_pct": round(v["abs_err"] / v["n"], 5), "wins": v["wins"], "beat_close": v["beat_close"]}
            for k, v in agg.items() if v["n"]]
    return sorted(rows, key=lambda r: r["mae_pct"])


def main() -> int:
    rows = snapshots()
    if not rows:
        print("no complete weekend yet (need weekend premiums + a Monday session print)"); return 0
    doc = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **score(rows)}
    out = DATA / "monday" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1))
    for wk in doc["weekends"]:
        print(f"\nMonday {wk['monday']}: {len(wk['assets'])} assets")
        for r in wk["issuers"]:
            print(f"  {r['issuer']:16} n={r['n']:<3} mae={r['mae_pct']*100:5.2f}%  wins={r['wins']:<3} beat_close={r['beat_close']}")
    print(f"\ncumulative -> {out}")
    for r in doc["cumulative"]:
        print(f"  {r['issuer']:16} n={r['n']:<3} mae={r['mae_pct']*100:5.2f}%  wins={r['wins']:<3} beat_close={r['beat_close']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
