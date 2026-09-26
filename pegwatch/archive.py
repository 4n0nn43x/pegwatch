"""Archive compaction: gzip every closed daily JSONL file. Run once a day from cron.

    python -m pegwatch.archive    # data/<name>/<day>.jsonl -> <day>.jsonl.gz for every day before yesterday

rwa_quotes alone grows ~75 MB a day and JSON lines compress about tenfold. Readers are unaffected: collect.latest only
reads the last two plain files (today and yesterday are never compacted), monday reads .jsonl and .jsonl.gz alike
(DuckDB decompresses on the fly). PEGWATCH_KEEP_DAYS=N also deletes archives older than N days (default 0: keep all).
"""

import gzip
import os
import shutil
import sys
from datetime import date, datetime, timedelta, timezone

from .collect import DATA

NAMES = ("rwa_quotes", "p2p", "ref_quotes", "premiums")
KEEP_DAYS = int(os.getenv("PEGWATCH_KEEP_DAYS", "0"))


def compact(today: date, keep_days: int = KEEP_DAYS) -> tuple[int, int]:
    """(files compacted, files deleted). Write to a temp file then rename: a crash never leaves a truncated archive."""
    done = deleted = 0
    for name in NAMES:
        for f in sorted((DATA / name).glob("*.jsonl")):
            if date.fromisoformat(f.stem) >= today - timedelta(days=1):
                continue                                      # today may still be appended to, yesterday feeds latest()
            gz, tmp = f.with_name(f.name + ".gz"), f.with_name(f.name + ".gz.tmp")
            with f.open("rb") as src, gzip.open(tmp, "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)
            os.replace(tmp, gz)
            f.unlink()
            done += 1
        if keep_days:
            for gz in (DATA / name).glob("*.jsonl.gz"):
                if date.fromisoformat(gz.name[:10]) < today - timedelta(days=keep_days):
                    gz.unlink()
                    deleted += 1
    return done, deleted


def main() -> int:
    done, deleted = compact(datetime.now(timezone.utc).date())
    print(f"{done} daily files compacted, {deleted} old archives deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
