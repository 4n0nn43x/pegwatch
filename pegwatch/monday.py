"""Monday scoreboard: who priced the weekend right? Run Monday after the open (and any time for the archive).

    python -m pegwatch.monday    # every weekend on disk -> data/monday/latest.json, prints the table

For each weekend and each asset: the last price of every wrapper while the reference was frozen (Sunday night for
stocks, Sunday before 18:00 ET for metals) vs the first real print after the weekend (Ostium session). The error of a
wrapper is sunday_price / monday_open - 1; the perp oracle (Hyperliquid, `proxy`) competes as "perps"; holding Friday's
close is the naive baseline. Tests CMC Research's peg-tightness ranking bStocks > xStocks > Ondo with real weekends.
Pure logic (score) has no I/O and is tested in tests/test_monday.py.

Memory stays flat as the archive grows: each weekend is queried on its own daily files only (3 premiums days, 3
ref_quotes days, plain or gzipped), and a closed weekend's rows are cached in data/monday/weekends/<monday>.json so it
is never queried again. Delete that folder after changing the SQL below.
"""

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .collect import DATA, db

NY = "America/New_York"
PERPS = "perps"          # the proxy competes under this issuer name
PREMIUM_DAYS = (-2, -1, 0)   # Sat, Sun, Mon UTC files hold every premium row of the NY weekend
REF_DAYS = (-1, 0, 1)        # Sun, Mon, Tue UTC files hold every Sunday/Monday NY reopen print


def day_files(name: str, monday: date, offsets: tuple[int, ...]) -> list[str]:
    """The daily files of data/<name>/ around one Monday, plain .jsonl or compacted .jsonl.gz."""
    days = [monday + timedelta(days=o) for o in offsets]
    return [str(f) for d in days for f in (DATA / name / f"{d}.jsonl", DATA / name / f"{d}.jsonl.gz") if f.exists()]


def mondays_on_disk() -> list[date]:
    """Every Monday that closes a weekend with at least one premiums file on disk."""
    days = {date.fromisoformat(f.name[:10]) for f in (DATA / "premiums").glob("*.jsonl*")}
    return sorted({d + timedelta(days=(7 - d.weekday()) % 7) for d in days if d.weekday() in (5, 6, 0)})


def snapshots(monday: date) -> list[dict]:
    """One row per wrapper for one weekend: last weekend snapshot before the reference reopened, joined with the open print."""
    pf, rf = day_files("premiums", monday, PREMIUM_DAYS), day_files("ref_quotes", monday, REF_DAYS)
    if not pf or not rf:
        return []
    pl, rl = ("[" + ", ".join(f"'{f}'" for f in fs) + "]" for fs in (pf, rf))
    rel = db().sql(f"""
        with p as (select *, ts::timestamptz at time zone '{NY}' as ny from read_json_auto({pl}, union_by_name=true) where regime = 'weekend'),
        r as (select ts, ticker, price, ts::timestamptz at time zone '{NY}' as ny from read_json_auto({rl}, union_by_name=true)
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


def all_rows(today: date) -> list[dict]:
    """Snapshot rows of every weekend on disk, closed weekends from the cache."""
    rows, cache = [], DATA / "monday" / "weekends"
    for mon in mondays_on_disk():
        f = cache / f"{mon}.json"
        if f.exists():
            rows += json.loads(f.read_text())
            continue
        got = snapshots(mon)
        if mon + timedelta(days=2) < today:      # the Tuesday UTC ref file is closed: the weekend is final
            cache.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(got))
        rows += got
    return rows


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
    rows = all_rows(datetime.now(timezone.utc).date())
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
