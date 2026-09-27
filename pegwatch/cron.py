"""Batch scheduler, one process under pm2. Replaces pm2 cron_restart, which on a still-running batch fails to kill it
and then refuses to start that app ever again (p2p on 2026-09-26, collect and ref on 2026-09-27).

A job whose previous run is still going skips its slot; a run older than its limit is killed.

    python -m pegwatch.cron
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone

from .collect import DATA

EVERY5 = range(0, 60, 5)
# name, module args, minutes of the hour, hour (None = every hour), time limit in seconds
JOBS = [
    ("p2p", ["pegwatch.p2p"], range(0, 60, 10), None, 580),   # up to 864 requests take 2 to 4 min, too close to a 5-min slot
    ("collect", ["pegwatch.collect"], EVERY5, None, 280),
    ("ref", ["pegwatch.ref"], EVERY5, None, 280),
    ("fixing", ["pegwatch.fixing"], range(1, 60, 5), None, 280),
    ("premiums", ["pegwatch.premiums"], range(2, 60, 5), None, 280),
    ("ladder", ["pegwatch.ladder"], range(3, 60, 5), None, 280),
    ("fixing-daily", ["pegwatch.fixing", "--daily"], [0], 12, 600),
    ("monday", ["pegwatch.monday"], [0], 14, 1800),    # after the 13:30 UTC NYSE open
    ("archive", ["pegwatch.archive"], [17], 3, 3000),  # gzip closed daily JSONL files, the archive would fill the disk otherwise
]


def due(now: datetime, minutes, hour) -> bool:
    return now.minute in minutes and (hour is None or now.hour == hour)


OUTPUTS = {"p2p snapshot": ("latest/p2p.jsonl", None), "dollar fixing": ("fixing/latest.json", "ts"),
           "wrapper premiums": ("premiums/latest.json", "ts"), "ladders": ("world.json", "ts"),
           "Monday scoreboard": ("monday/latest.json", "ts"), "exchange USDT price": ("cmc_fx.json", "ts")}


def iso(t: float | None) -> str | None:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def outputs() -> dict:
    """Age of each public output, from its own ts when it has one, else the file's mtime."""
    out = {}
    for label, (path, field) in OUTPUTS.items():
        f = DATA / path
        if not f.exists():
            out[label] = {"path": path, "ts": None}
            continue
        ts = json.loads(f.read_text()).get(field) if field else None
        out[label] = {"path": path, "ts": ts or iso(f.stat().st_mtime)}
    return out


def write_status(jobs: dict) -> None:
    doc = {"ts": iso(time.time()), "jobs": jobs, "outputs": outputs()}
    tmp = DATA / "status.json.tmp"
    tmp.write_text(json.dumps(doc, indent=1))
    tmp.replace(DATA / "status.json")


def main() -> int:
    running: dict[str, tuple[subprocess.Popen, float]] = {}
    jobs = {name: {"every": "daily %02d:%02d UTC" % (hour, minutes[0]) if hour is not None else f"{minutes[1] - minutes[0]} min",
                   "last_start": None, "last_exit": None, "last_seconds": None, "skipped": 0, "killed": 0}
            for name, _, minutes, hour, _ in JOBS}

    def start(name, args):
        if name in running and running[name][0].poll() is None:
            print(f"{name}: previous run still going, slot skipped", flush=True)
            jobs[name]["skipped"] += 1
            return
        running[name] = (subprocess.Popen([sys.executable, "-m", *args]), time.monotonic())
        jobs[name].update(last_start=iso(time.time()), last_exit=None, last_seconds=None)

    for name, args, _, hour, _ in JOBS:          # the 5-min jobs run once at boot, the daily ones wait for their slot
        if hour is None:
            start(name, args)
    while True:
        time.sleep(60 - time.time() % 60 + 0.5)   # just after each minute boundary
        now = datetime.now(timezone.utc)
        for name, args, minutes, hour, limit in JOBS:
            p = running.get(name)
            if p and p[0].poll() is None and time.monotonic() - p[1] > limit:
                print(f"{name}: over {limit}s, killed", flush=True)
                p[0].kill()
                p[0].wait()
                jobs[name]["killed"] += 1
            if p and p[0].poll() is not None and jobs[name]["last_exit"] is None:   # seconds rounded up to the minute check
                jobs[name].update(last_exit=p[0].returncode, last_seconds=round(time.monotonic() - p[1]))
            if due(now, minutes, hour):
                start(name, args)
        try:
            write_status(jobs)
        except Exception as e:                   # a status page must never stop the batches
            print(f"status: {e}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
