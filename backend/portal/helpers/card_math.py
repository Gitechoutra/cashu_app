"""Credit calculations. Pure functions on Decimal — no floats, no I/O.

Credit utilisation = outstanding / limit × 100
Estimated available = limit − outstanding

The issuer-reported available credit always wins over the estimate: it already
reflects pending transactions, holds, refunds, fees and issuer-specific rules
that this app cannot see.
"""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from portal.models.base import utcnow

ZERO = Decimal('0')
PCT = Decimal('0.01')
DUE_SOON_DAYS = 5


def _d(v):
    return None if v is None else Decimal(str(v))


def utilization_pct(outstanding, credit_limit):
    """None when it cannot be computed honestly (unknown values or zero limit)."""
    outstanding, credit_limit = _d(outstanding), _d(credit_limit)
    if outstanding is None or credit_limit is None or credit_limit <= ZERO:
        return None
    if outstanding <= ZERO:            # credit balance / fully paid
        return Decimal('0.00')
    return (outstanding / credit_limit * 100).quantize(PCT, rounding=ROUND_HALF_UP)


def available_credit(credit_limit, outstanding, reported=None):
    """Returns (value, basis, over_limit) with basis REPORTED | ESTIMATED | UNKNOWN."""
    reported = _d(reported)
    if reported is not None:
        return reported, 'REPORTED', reported < ZERO
    credit_limit, outstanding = _d(credit_limit), _d(outstanding)
    if credit_limit is None or outstanding is None:
        return None, 'UNKNOWN', False
    est = credit_limit - outstanding
    return max(est, ZERO), 'ESTIMATED', est < ZERO


def utilization_band(pct):
    if pct is None:
        return 'UNKNOWN'
    if pct < 10:
        return 'EXCELLENT'
    if pct < 30:
        return 'GOOD'
    if pct < 50:
        return 'FAIR'
    return 'HIGH'


def bill_status(outstanding, due_date, today=None, paid_in_app=ZERO):
    """Derived status of the current bill. Payments made in-app only count as
    'payment initiated' — the issuer confirms the bill as paid, not us."""
    today = today or date.today()
    outstanding = _d(outstanding)
    if outstanding is None or due_date is None:
        return 'UNKNOWN'
    if outstanding <= ZERO:
        return 'NO_DUES'
    if _d(paid_in_app) and _d(paid_in_app) >= outstanding:
        return 'PAYMENT_INITIATED'
    if due_date < today:
        return 'OVERDUE'
    if due_date <= today + timedelta(days=DUE_SOON_DAYS):
        return 'DUE_SOON'
    return 'DUE'


def is_stale(data_as_of, max_age_hours, now=None):
    if data_as_of is None:
        return True
    now = now or utcnow()
    return now - data_as_of > timedelta(hours=max_age_hours)


def money(v):
    """Serialise Decimal → string with 2dp (JSON-safe, no float rounding)."""
    if v is None:
        return None
    return str(Decimal(str(v)).quantize(PCT, rounding=ROUND_HALF_UP))
