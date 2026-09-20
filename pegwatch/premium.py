"""Reference price selection and premium computation. Pure logic, no I/O."""

from dataclasses import dataclass
from datetime import datetime

from .regime import regime, is_market_closed, SESSION


@dataclass(frozen=True)
class RefQuote:
    """What we know about the underlying at an instant."""
    last_close: float            # last regular-session close
    extended: float | None = None  # latest pre/post-market print, if the source gives one
    session: float | None = None   # latest regular-session print (during session)


@dataclass(frozen=True)
class Premium:
    ref_price: float
    ref_session: str     # "session" | "extended" | "close": which reference was used
    regime: str
    premium_pct: float


def pick_reference(q: RefQuote, r: str) -> tuple[float, str]:
    if r == SESSION and q.session is not None:
        return q.session, "session"
    if not is_market_closed(r) and q.extended is not None:
        return q.extended, "extended"
    return q.last_close, "close"


def premium(token_price: float, q: RefQuote, ts: datetime) -> Premium:
    if token_price <= 0 or q.last_close <= 0:
        raise ValueError("prices must be positive")
    r = regime(ts)
    ref, which = pick_reference(q, r)
    return Premium(ref_price=ref, ref_session=which, regime=r, premium_pct=token_price / ref - 1)


def wrapper_spread(prices: dict[str, float]) -> float:
    """Max relative gap between wrappers quoting the same asset at the same instant."""
    if len(prices) < 2:
        return 0.0
    lo, hi = min(prices.values()), max(prices.values())
    return hi / lo - 1
