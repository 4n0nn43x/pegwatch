from datetime import datetime

from pegwatch.cron import JOBS, due

SLOTS = {name: (minutes, hour) for name, _, minutes, hour, _ in JOBS}


def test_slots():
    at = lambda h, m: datetime(2026, 9, 27, h, m)
    assert due(at(10, 20), *SLOTS["p2p"]) and not due(at(10, 21), *SLOTS["p2p"])
    assert due(at(10, 22), *SLOTS["premiums"]) and due(at(10, 21), *SLOTS["fixing"])
    assert due(at(12, 0), *SLOTS["fixing-daily"]) and not due(at(13, 0), *SLOTS["fixing-daily"])
    assert all(limit < 300 for _, _, _, hour, limit in JOBS if hour is None)   # a 5-min job ends before its next slot
