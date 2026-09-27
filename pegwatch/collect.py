"""Collector: pull CMC RWA quotes and append raw JSON lines. Run every 5 min from cron.

    python -m pegwatch.collect          # one cycle
    python -m pegwatch.collect --probe  # only check key + RWA access (go/no-go)
"""

import hashlib
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
    evidence(path, r, body, params)
    st = body.get("status", {})
    if r.status_code != 200 or str(st.get("error_code", "0")) != "0":
        raise RuntimeError(f"{path} -> HTTP {r.status_code} error_code={st.get('error_code')} {st.get('error_message')}")
    return body


def evidence(path: str, r, body: dict, params: dict, keep: int = 3) -> None:
    """The evidence drawer: last real request and response per CMC endpoint in data/evidence/latest.json, key masked,
    response lists cut to `keep` items with their full length noted. The site shows it under every CMC-based number."""
    out = DATA / "evidence" / "latest.json"
    try:
        doc = json.loads(out.read_text()) if out.exists() else {}
    except ValueError:
        doc = {}
    sample = {k: ({kk: (vv[:keep] if isinstance(vv, list) else vv) for kk, vv in v.items()} if isinstance(v, dict) else v)
              for k, v in body.items()}
    lists = {f"data.{kk}": len(vv) for v in body.values() if isinstance(v, dict) for kk, vv in v.items() if isinstance(vv, list)}
    short = {k: ",".join(str(v).split(",")[:5]) for k, v in params.items()}    # a copy-pastable request: first 5 ids only
    url = r.url if len(r.url) <= 200 else r.url[:200] + f"...(+{len(r.url) - 200} chars)"
    doc[path] = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "method": "GET", "url": url,
                 "headers": {"X-CMC_PRO_API_KEY": "••••••••", "Accept": "application/json"},
                 "http_status": r.status_code, "elapsed_ms": round(r.elapsed.total_seconds() * 1000),
                 "credit_count": body.get("status", {}).get("credit_count"), "bytes": len(r.content),
                 "sha256": hashlib.sha256(r.content).hexdigest(), "list_lengths": lists, "response_sample": sample,
                 "curl": "curl -H \"X-CMC_PRO_API_KEY: $CMC_API_KEY\" '" + requests.Request("GET", BASE + path, params=short).prepare().url + "'"}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1))


def append(name: str, rows: list[dict]) -> Path:
    """Append rows as JSON lines into data/<name>/<YYYY-MM-DD>.jsonl (DuckDB reads these directly)."""
    ts = datetime.now(timezone.utc)
    out = DATA / name / f"{ts:%Y-%m-%d}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps({"ts": ts.isoformat(), **row}, separators=(",", ":")) + "\n" for row in rows)
    with out.open("a") as f:
        f.write(lines)
    snap = DATA / "latest" / f"{name}.jsonl"          # the last cycle alone, so latest() never parses a day's archive
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.with_suffix(".tmp").write_text(lines)
    os.replace(snap.with_suffix(".tmp"), snap)
    return out


def db():
    """DuckDB with the session clock on UTC: JSONL `ts` values parse as naive UTC timestamps, so every timezone
    conversion and strftime must start from UTC whatever the host's TZ (the VPS is UTC, a laptop is not)."""
    import duckdb
    duckdb.sql("set timezone = 'UTC'")
    return duckdb


def latest(name: str) -> tuple[str, list[dict]]:
    """Rows of the most recent snapshot of data/<name>, ts as ISO string. ("", []) when nothing yet.

    Reads data/latest/<name>.jsonl, the last cycle written by append(). Scanning the daily archive instead
    (up to 800 MB a day for p2p) made the batches outlive their 5-min cron and wedged pm2 on 2026-09-26.
    """
    snap = DATA / "latest" / f"{name}.jsonl"
    if not snap.exists():
        return "", []
    rows = [json.loads(line) for line in snap.read_text().splitlines() if line]
    for r in rows:
        r["ts"] = datetime.fromisoformat(r["ts"]).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (rows[0]["ts"] if rows else ""), rows


USDT_ID = 825
FX_MAX_AGE = 6 * 3600   # 1 credit per fiat converted: 37 fiats every 6 h stays inside the Basic plan with the 5-min RWA cycle


def cached(name: str, max_age: float, fetch) -> dict:
    """data/<name>.json if younger than max_age seconds, else fetch() stamped with ts and saved. Keeps credit use flat."""
    out = DATA / f"{name}.json"
    if out.exists():
        doc = json.loads(out.read_text())
        if time.time() - datetime.fromisoformat(doc["ts"]).timestamp() < max_age:
            return doc
    doc = {"ts": datetime.now(timezone.utc).isoformat(), **fetch()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1))
    return doc


def usdt_in_fiats() -> dict:
    """CMC's own USDT price in each of our P2P fiats that CMC lists, the third leg next to P2P and the official rate.
    {"ts", "prices": {fiat: price}, "unsupported": [fiats CMC does not list]}."""
    from .p2p import FIATS

    def fetch():
        listed = {f["symbol"] for f in get("/v1/fiat/map", limit=5000)["data"]}
        ok = [f for f in FIATS if f in listed]
        quote = get("/v2/cryptocurrency/quotes/latest", id=USDT_ID, convert=",".join(ok))["data"][str(USDT_ID)]["quote"]
        return {"prices": {f: q["price"] for f, q in quote.items()}, "unsupported": [f for f in FIATS if f not in listed]}
    return cached("cmc_fx", FX_MAX_AGE, fetch)


def rwa_issuers() -> dict:
    """Every RWA issuer CMC tracks, with its token count: the denominator of our access matrix. 1 credit a day."""
    return cached("cmc_issuers", 24 * 3600,
                  lambda: {"issuers": get("/v5/real-world-assets/issuers/list", limit=100)["data"]["issuers"]})


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
