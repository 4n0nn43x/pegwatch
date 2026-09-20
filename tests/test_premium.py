from datetime import datetime, timezone

import pytest

from pegwatch.regime import regime, SESSION, PRE, POST, NIGHT, WEEKEND, HOLIDAY
from pegwatch.premium import RefQuote, premium, wrapper_spread


def utc(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


@pytest.mark.parametrize("ts,expected", [
    (utc(2026, 9, 14, 14, 0), SESSION),   # Mon 10:00 NY (EDT)
    (utc(2026, 9, 14, 12, 0), PRE),       # Mon 08:00 NY
    (utc(2026, 9, 14, 21, 0), POST),      # Mon 17:00 NY
    (utc(2026, 9, 15, 2, 0), NIGHT),      # Mon 22:00 NY
    (utc(2026, 9, 12, 15, 0), WEEKEND),   # Sat
    (utc(2026, 9, 7, 15, 0), HOLIDAY),    # Labor Day
    (utc(2026, 9, 14, 13, 30), SESSION),  # exactly 09:30 NY opens
    (utc(2026, 9, 14, 20, 0), POST),      # exactly 16:00 NY closes
])
def test_regime(ts, expected):
    assert regime(ts) == expected


def test_regime_rejects_naive():
    with pytest.raises(ValueError):
        regime(datetime(2026, 9, 14, 14, 0))


def test_weekend_uses_close_even_if_extended_present():
    q = RefQuote(last_close=100.0, extended=108.0)
    p = premium(104.0, q, utc(2026, 9, 12, 15, 0))
    assert p.ref_session == "close" and p.ref_price == 100.0
    assert p.premium_pct == pytest.approx(0.04)


def test_after_hours_uses_extended_to_avoid_fake_premium():
    # earnings at 16:05: stock jumps to 108 after hours, token follows at 108.5
    q = RefQuote(last_close=100.0, extended=108.0)
    p = premium(108.5, q, utc(2026, 9, 14, 21, 0))
    assert p.ref_session == "extended"
    assert p.premium_pct == pytest.approx(0.5 / 108.0)


def test_after_hours_without_extended_falls_back_to_close():
    p = premium(108.5, RefQuote(last_close=100.0), utc(2026, 9, 14, 21, 0))
    assert p.ref_session == "close" and p.premium_pct == pytest.approx(0.085)


def test_session_prefers_live_print():
    q = RefQuote(last_close=100.0, extended=101.0, session=102.0)
    p = premium(102.0, q, utc(2026, 9, 14, 14, 0))
    assert p.ref_session == "session" and p.premium_pct == pytest.approx(0.0)


def test_wrapper_spread():
    assert wrapper_spread({"xstocks": 104.0, "ondo": 101.5, "bstocks": 100.0}) == pytest.approx(0.04)
    assert wrapper_spread({"xstocks": 104.0}) == 0.0
