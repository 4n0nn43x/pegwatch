"""NYSE trading regime for a given instant. Pure logic, no I/O."""

from datetime import datetime, date, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# ponytail: hard-coded NYSE full-day closures, extend yearly. Early closes ignored.
HOLIDAYS = {
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
    date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
    date(2027, 11, 25), date(2027, 12, 24),
}

PRE_OPEN, OPEN, CLOSE, POST_CLOSE = time(4, 0), time(9, 30), time(16, 0), time(20, 0)

SESSION, PRE, POST, NIGHT, WEEKEND, HOLIDAY = "session", "pre", "post", "night", "weekend", "holiday"


def regime(ts: datetime) -> str:
    """Classify a timezone-aware instant into a US equity trading regime."""
    if ts.tzinfo is None:
        raise ValueError("ts must be timezone-aware")
    ny = ts.astimezone(NY)
    if ny.weekday() >= 5:
        return WEEKEND
    if ny.date() in HOLIDAYS:
        return HOLIDAY
    t = ny.time()
    if OPEN <= t < CLOSE:
        return SESSION
    if PRE_OPEN <= t < OPEN:
        return PRE
    if CLOSE <= t < POST_CLOSE:
        return POST
    return NIGHT


def is_market_closed(r: str) -> bool:
    """True when no TradFi print exists at all: reference must be the last close."""
    return r in (NIGHT, WEEKEND, HOLIDAY)
