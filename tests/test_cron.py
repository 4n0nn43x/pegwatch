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
