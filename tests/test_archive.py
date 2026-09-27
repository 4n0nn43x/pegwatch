import gzip
from datetime import date

import pegwatch.archive as a


def test_compact_keeps_today_and_yesterday_plain(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "DATA", tmp_path)
    d = tmp_path / "rwa_quotes"
    d.mkdir()
    for day in ("2026-09-20", "2026-09-24", "2026-09-25", "2026-09-26"):
        (d / f"{day}.jsonl").write_text(f'{{"day": "{day}"}}\n')
    assert a.compact(date(2026, 9, 26)) == (2, 0)
    assert sorted(f.name for f in d.iterdir()) == ["2026-09-20.jsonl.gz", "2026-09-24.jsonl.gz", "2026-09-25.jsonl", "2026-09-26.jsonl"]
    assert gzip.open(d / "2026-09-20.jsonl.gz", "rt").read() == '{"day": "2026-09-20"}\n'
    assert a.compact(date(2026, 9, 26), keep_days=5) == (0, 1)                # 09-20 is older than 5 days
    assert not (d / "2026-09-20.jsonl.gz").exists()


def test_keep_days_boundary_and_other_stores(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "DATA", tmp_path)
    for name in a.NAMES:
        (tmp_path / name).mkdir()
    (tmp_path / "p2p" / "2026-09-24.jsonl").write_text("x\n")
    (tmp_path / "premiums" / "2026-09-16.jsonl.gz").write_bytes(gzip.compress(b"x\n"))   # exactly 10 days old: kept
    (tmp_path / "premiums" / "2026-09-15.jsonl.gz").write_bytes(gzip.compress(b"x\n"))
    assert a.compact(date(2026, 9, 26), keep_days=10) == (1, 1)
    assert sorted(f.name for f in (tmp_path / "premiums").iterdir()) == ["2026-09-16.jsonl.gz"]
    assert [f.name for f in (tmp_path / "p2p").iterdir()] == ["2026-09-24.jsonl.gz"]
