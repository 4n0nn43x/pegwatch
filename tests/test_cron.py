from datetime import datetime

from pegwatch.cron import JOBS, due

SLOTS = {name: (minutes, hour) for name, _, minutes, hour, _ in JOBS}


def test_slots():
    at = lambda h, m: datetime(2026, 9, 27, h, m)
    assert due(at(10, 20), *SLOTS["p2p"]) and not due(at(10, 25), *SLOTS["p2p"])
    assert due(at(10, 22), *SLOTS["premiums"]) and due(at(10, 21), *SLOTS["fixing"])
    assert due(at(12, 0), *SLOTS["fixing-daily"]) and not due(at(13, 0), *SLOTS["fixing-daily"])
    for _, _, minutes, hour, limit in JOBS:
        if hour is None:                                   # a run is killed before its next slot comes
            assert limit < 60 * (minutes[1] - minutes[0])


def test_job_table_sanity():
    from importlib.util import find_spec
    assert len({j[0] for j in JOBS}) == len(JOBS)
    for name, args, minutes, hour, limit in JOBS:
        assert find_spec(args[0]) is not None, name
        assert all(0 <= m < 60 for m in minutes) and (hour is None or 0 <= hour < 24)
        assert 0 < limit < 24 * 3600


def test_derived_jobs_run_after_their_inputs():
    # collect/ref at :00, fixing :01, premiums :02, ladder :03 within each 5-min block
    first = {name: min(minutes) for name, _, minutes, _, _ in JOBS}
    assert first["collect"] == first["ref"] < first["fixing"] < first["premiums"] < first["ladder"] < 5


def test_status_reports_output_ages_and_survives_missing_files(tmp_path, monkeypatch):
    import json
    import pegwatch.cron as c
    monkeypatch.setattr(c, "DATA", tmp_path)
    monkeypatch.setattr(c, "credits", lambda: {"used_today": 12})
    (tmp_path / "fixing").mkdir()
    (tmp_path / "fixing" / "latest.json").write_text('{"ts": "2026-09-27T11:10:15Z"}')
    c.write_status({"p2p": {"skipped": 1}})
    doc = json.loads((tmp_path / "status.json").read_text())
    assert doc["outputs"]["dollar fixing"]["ts"] == "2026-09-27T11:10:15Z"
    assert doc["outputs"]["wrapper premiums"]["ts"] is None               # missing file: reported, not a crash
    assert doc["jobs"]["p2p"]["skipped"] == 1 and doc["cmc_credits"] == {"used_today": 12}
