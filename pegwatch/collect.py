"""Collector: pull CMC RWA quotes and append raw JSON lines. Run every 5 min from cron.

    python -m pegwatch.collect          # one cycle
    python -m pegwatch.collect --probe  # only check key + RWA access (go/no-go)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = "https://pro-api.coinmarketcap.com"
DATA = Path(os.getenv("PEGWATCH_DATA", "data"))
TOP_N = int(os.getenv("PEGWATCH_TOP_N", "200"))
S = requests.Session()
S.headers["X-CMC_PRO_API_KEY"] = os.environ.get("CMC_API_KEY", "")
S.headers["Accept"] = "application/json"


def get(path: str, **params) -> dict:
    r = S.get(BASE + path, params=params, timeout=30)
    body = r.json()
    st = body.get("status", {})
    if r.status_code != 200 or str(st.get("error_code", "0")) != "0":
        raise RuntimeError(f"{path} -> HTTP {r.status_code} error_code={st.get('error_code')} {st.get('error_message')}")
    return body


def append(name: str, rows: list[dict]) -> Path:
    """Append rows as JSON lines into data/<name>/<YYYY-MM-DD>.jsonl (DuckDB reads these directly)."""
    ts = datetime.now(timezone.utc)
    out = DATA / name / f"{ts:%Y-%m-%d}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as f:
        for row in rows:
            f.write(json.dumps({"ts": ts.isoformat(), **row}, separators=(",", ":")) + "\n")
    return out


def db():
    """DuckDB with the session clock on UTC: JSONL `ts` values parse as naive UTC timestamps, so every timezone
    conversion and strftime must start from UTC whatever the host's TZ (the VPS is UTC, a laptop is not)."""
    import duckdb
    duckdb.sql("set timezone = 'UTC'")
    return duckdb


def latest(name: str, where: str = "true") -> tuple[str, list[dict]]:
    """Rows of the most recent snapshot in data/<name>/*.jsonl, ts as ISO string. ("", []) when nothing yet."""
    if not list((DATA / name).glob("*.jsonl")):
        return "", []
    files = str(DATA / name / "*.jsonl")
    rel = db().sql(f"select * replace (strftime(ts, '%Y-%m-%dT%H:%M:%SZ') as ts) "
                   f"from read_json_auto('{files}') where ts = (select max(ts) from read_json_auto('{files}')) and {where}")
    rows = [dict(zip(rel.columns, r)) for r in rel.fetchall()]
    return (rows[0]["ts"] if rows else ""), rows


def probe() -> int:
    """Go/no-go: key valid? RWA endpoints reachable? Prints the verdict, returns exit code."""
    try:
        info = get("/v1/key/info")["data"]
        plan = info.get("plan", {})
        print(f"key OK: plan={plan.get('name')} credits/month={plan.get('credit_limit_monthly')} "
              f"used today={info.get('usage', {}).get('current_day', {}).get('credits_used')}")
    except Exception as e:
        print("key KO:", e); return 2
    try:
        m = get("/v5/real-world-assets/map", limit=5)["data"]["rwa_assets"]
        print(f"RWA OK: map returned {len(m)} rows, first={m[0] if m else None}")
    except Exception as e:
        print("RWA KO (the 402/1003 bug from the Q&A?):", e); return 3
    return 0


def cycle() -> None:
    ids = [a["rwa_id"] for a in get("/v5/real-world-assets/map", limit=TOP_N, has_tokens="true")["data"]["rwa_assets"]]
    rows, credits = [], 0
    for i in range(0, len(ids), 250):
        body = get("/v5/real-world-assets/quotes/latest", rwa_id=",".join(map(str, ids[i:i + 250])))
        rows.extend(body["data"]["rwa_assets"])
        credits += body["status"]["credit_count"]
        time.sleep(0.5)
    out = append("rwa_quotes", rows)
    print(f"{len(rows)} assets, {credits} credits -> {out}")


if __name__ == "__main__":
    sys.exit(probe() if "--probe" in sys.argv else cycle())
