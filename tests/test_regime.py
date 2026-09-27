from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from pegwatch.regime import regime, is_market_closed, SESSION, PRE, POST, NIGHT, WEEKEND, HOLIDAY


def utc(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


@pytest.mark.parametrize("ts,expected", [
    (utc(2026, 9, 14, 13, 29), PRE),      # 09:29 EDT, one minute before the open
    (utc(2026, 9, 14, 19, 59), SESSION),  # 15:59 EDT
    (utc(2026, 9, 14, 8, 0), PRE),        # 04:00 EDT, pre-market opens
    (utc(2026, 9, 14, 7, 59), NIGHT),
    (utc(2026, 9, 14, 23, 59), POST),     # 19:59 EDT
    (utc(2026, 9, 15, 0, 0), NIGHT),      # 20:00 EDT, after-hours over
    # DST ended 2026-11-01: the open moves to 14:30 UTC
    (utc(2026, 11, 2, 13, 30), PRE),      # 08:30 EST
    (utc(2026, 11, 2, 14, 30), SESSION),  # 09:30 EST
    (utc(2026, 11, 2, 20, 30), SESSION),  # 15:30 EST, would be post under EDT
    (utc(2026, 11, 2, 21, 0), POST),      # 16:00 EST
    # DST started 2026-03-08: the Friday before opens at 14:30 UTC, the Monday after at 13:30 UTC
    (utc(2026, 3, 6, 13, 30), PRE),
    (utc(2026, 3, 9, 13, 30), SESSION),
    # the weekend is a New York weekend, not a UTC one
    (utc(2026, 9, 12, 0, 30), NIGHT),     # Sat UTC, still Fri 20:30 NY
    (utc(2026, 9, 11, 23, 0), POST),      # Fri 19:00 NY
    (utc(2026, 9, 14, 0, 30), WEEKEND),   # Mon UTC, still Sun 20:30 NY
    (utc(2026, 9, 14, 4, 30), NIGHT),     # Mon 00:30 NY
    # holidays win over every intraday regime, early closes are ignored
    (utc(2026, 11, 26, 15, 0), HOLIDAY),  # Thanksgiving
    (utc(2026, 11, 27, 15, 0), SESSION),  # day after Thanksgiving: early close, still a session day
    (utc(2026, 9, 7, 22, 0), HOLIDAY),    # Labor Day evening is not "post"
    (utc(2026, 4, 3, 15, 0), HOLIDAY),    # Good Friday
    (utc(2027, 12, 24, 15, 0), HOLIDAY),  # Christmas 2027 falls on Saturday, observed Friday
    (utc(2026, 7, 3, 15, 0), HOLIDAY),    # July 4 2026 is a Saturday, observed Friday
])
def test_regime_boundaries(ts, expected):
    assert regime(ts) == expected


def test_any_timezone_is_converted_to_new_york():
    assert regime(datetime(2026, 9, 14, 23, 0, tzinfo=ZoneInfo("Asia/Tokyo"))) == SESSION   # 10:00 NY


def test_is_market_closed():
    assert {r for r in (SESSION, PRE, POST, NIGHT, WEEKEND, HOLIDAY) if is_market_closed(r)} == {NIGHT, WEEKEND, HOLIDAY}
