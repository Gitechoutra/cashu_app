from datetime import date, datetime, timedelta
from decimal import Decimal as D

from portal.helpers import card_math as cm
from portal.helpers.validators import validate_amount, validate_last4, validate_pin, normalize_mobile


def test_utilization_basic():
    assert cm.utilization_pct(D('45000'), D('200000')) == D('22.50')
    assert cm.utilization_pct(D('1'), D('3')) == D('33.33')


def test_utilization_zero_limit_does_not_divide():
    assert cm.utilization_pct(D('100'), D('0')) is None


def test_utilization_unknown_values():
    assert cm.utilization_pct(None, D('1000')) is None
    assert cm.utilization_pct(D('10'), None) is None


def test_utilization_credit_balance_is_zero():
    assert cm.utilization_pct(D('-500'), D('1000')) == D('0.00')


def test_utilization_over_limit_exceeds_100():
    assert cm.utilization_pct(D('1100'), D('1000')) == D('110.00')


def test_available_prefers_reported_value():
    assert cm.available_credit(D('100000'), D('20000'), reported=D('75000')) == (D('75000'), 'REPORTED', False)


def test_available_estimated_and_over_limit():
    assert cm.available_credit(D('100000'), D('20000')) == (D('80000'), 'ESTIMATED', False)
    assert cm.available_credit(D('1000'), D('1200')) == (D('0'), 'ESTIMATED', True)
    assert cm.available_credit(None, D('10')) == (None, 'UNKNOWN', False)


def test_bill_status():
    t = date(2026, 10, 9)
    assert cm.bill_status(D('0'), t, today=t) == 'NO_DUES'
    assert cm.bill_status(D('10'), t - timedelta(days=1), today=t) == 'OVERDUE'
    assert cm.bill_status(D('10'), t + timedelta(days=2), today=t) == 'DUE_SOON'
    assert cm.bill_status(D('10'), t + timedelta(days=20), today=t) == 'DUE'
    assert cm.bill_status(D('10'), t, today=t, paid_in_app=D('10')) == 'PAYMENT_INITIATED'
    assert cm.bill_status(None, t, today=t) == 'UNKNOWN'


def test_staleness():
    now = datetime(2026, 10, 9, 12)
    assert cm.is_stale(now - timedelta(hours=25), 24, now=now)
    assert not cm.is_stale(now - timedelta(hours=1), 24, now=now)
    assert cm.is_stale(None, 24, now=now)


def test_amount_validation():
    assert validate_amount('1,50,000.50', 'x') == (D('150000.50'), None)
    assert validate_amount('-5', 'x')[1]
    assert validate_amount('1e5', 'x')[1]
    assert validate_amount('10.555', 'x')[1]
    assert validate_amount('0', 'x', allow_zero=False)[1]
    assert validate_amount(True, 'x')[1]
    assert validate_amount('99999999999', 'x')[1]


def test_last4_pin_mobile_validation():
    assert validate_last4('0042') == ('0042', None)
    for bad in ('424', '42424', '42a4', ''):
        assert validate_last4(bad)[1]
    assert validate_pin('4826') == ('4826', None)
    for weak in ('1111', '1234', '9876', '12'):
        assert validate_pin(weak)[1]
    assert normalize_mobile('+91 98765 43210') == ('+919876543210', None)
    assert normalize_mobile('5876543210')[1]
