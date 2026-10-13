import hashlib
import hmac
import json

import pytest

from portal.models.payment_transactions import PaymentTransactions

from .conftest import auth, idem, login, manual_card


class FakeRazorpay:
    """Stands in for Razorpay's REST API. Payment status is whatever the
    'gateway' says — the tests prove the app only trusts this server-side view."""

    def __init__(self):
        self.orders, self.payments, self.n = {}, {}, 0

    def create_order(self, amount_paise, receipt, notes):
        self.n += 1
        oid = f'order_T{self.n:04d}'
        self.orders[oid] = amount_paise
        return {'id': oid, 'amount': amount_paise, 'currency': 'INR', 'receipt': receipt}

    def pay(self, oid, status='captured', amount=None):
        pid = f'pay_T{len(self.payments) + 1:04d}'
        self.payments[pid] = {'id': pid, 'order_id': oid, 'amount': amount or self.orders[oid],
                              'currency': 'INR', 'status': status, 'method': 'upi'}
        return pid

    def fetch_payment(self, pid):
        return self.payments[pid]

    def fetch_order_payments(self, oid):
        return [p for p in self.payments.values() if p['order_id'] == oid]


@pytest.fixture
def gw(monkeypatch):
    g = FakeRazorpay()
    for fn in ('create_order', 'fetch_payment', 'fetch_order_payments'):
        monkeypatch.setattr(f'portal.helpers.razorpay_helper.{fn}', getattr(g, fn))
    return g


def sig(oid, pid, secret='test_secret'):
    return hmac.new(secret.encode(), f'{oid}|{pid}'.encode(), hashlib.sha256).hexdigest()


def setup_card(app, sent_otps, **over):
    c, t = login(app, sent_otps)
    card = manual_card(c, t, **over).json['response']['card']
    return c, t, card['card_id']


def start(c, t, card_id, amount='5000', key=None):
    return c.post('/v1/bills/payment-session', json={'card_id': card_id, 'amount': amount,
                                                      'idempotency_key': key or idem()}, headers=auth(t))


def test_bills_list(app, sent_otps):
    c, t, card_id = setup_card(app, sent_otps)
    r = c.get('/v1/bills', headers=auth(t)).json['response']
    assert r['bills'][0]['card_id'] == card_id and r['bills'][0]['outstanding_balance'] == '45000.50'
    assert r['payment']['configured'] and r['payment']['mode'] == 'test'
    assert 'key_secret' not in json.dumps(r) and 'test_secret' not in json.dumps(r)


def test_payment_not_configured(app, sent_otps):
    c, t, card_id = setup_card(app, sent_otps)
    app.config['RAZORPAY_KEY_SECRET'] = ''
    try:
        r = start(c, t, card_id)
        assert r.status_code == 503 and r.json['response']['code'] == 'PAYMENT_NOT_CONFIGURED'
        assert c.get('/v1/bills', headers=auth(t)).json['response']['payment']['configured'] is False
    finally:
        app.config['RAZORPAY_KEY_SECRET'] = 'test_secret'


def test_live_keys_refused_without_bill_settlement(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    app.config['RAZORPAY_KEY_ID'] = 'rzp_live_xxx'
    try:
        r = start(c, t, card_id)
        assert r.status_code == 503 and 'BBPS' in r.json['response']['message']
    finally:
        app.config['RAZORPAY_KEY_ID'] = 'rzp_test_dummy'


def test_create_session_and_double_submit_is_idempotent(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    key = idem()
    r1 = start(c, t, card_id, key=key)
    assert r1.status_code == 201, r1.json
    body = r1.json['response']
    assert body['checkout']['amount'] == 500000 and body['checkout']['key'] == 'rzp_test_dummy'
    assert body['payment']['status'] == 'CREATED'
    r2 = start(c, t, card_id, key=key)
    assert r2.json['response']['payment']['payment_id'] == body['payment']['payment_id']
    assert PaymentTransactions.query.count() == 1 and gw.n == 1
    r3 = start(c, t, card_id, amount='6000', key=key)
    assert r3.status_code == 409


def test_amount_validation(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    for amt in ('0', '-10', '0.5', '45000.51', '12.345', 'abc'):
        assert start(c, t, card_id, amount=amt).status_code == 400, amt
    assert start(c, t, card_id, amount='45000.50').status_code == 201


def test_verify_success_marks_captured_but_not_issuer_settled(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    oid = start(c, t, card_id).json['response']['checkout']['order_id']
    pid = gw.pay(oid)
    r = c.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid, 'razorpay_payment_id': pid,
                                                  'razorpay_signature': sig(oid, pid)}, headers=auth(t))
    p = r.json['response']['payment']
    assert r.status_code == 200 and p['status'] == 'SUCCESS' and p['provider_payment_id'] == pid
    assert p['settlement_status'] == 'NOT_CONFIGURED' and p['receipt_number'].startswith('CV')
    card = c.get(f'/v1/cards/{card_id}', headers=auth(t)).json['response']['card']
    assert card['outstanding_balance'] == '45000.50'          # issuer figures are NOT faked down
    assert card['paid_in_app_this_cycle'] == '5000.00'


def test_forged_signature_cannot_mark_success(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    oid = start(c, t, card_id).json['response']['checkout']['order_id']
    r = c.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid, 'razorpay_payment_id': 'pay_fake',
                                                  'razorpay_signature': 'deadbeef', 'status': 'SUCCESS'},
               headers=auth(t))
    assert r.status_code == 400
    assert PaymentTransactions.query.first().status == 'CREATED'


def test_valid_signature_but_gateway_says_failed(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    oid = start(c, t, card_id).json['response']['checkout']['order_id']
    pid = gw.pay(oid, status='failed')
    r = c.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid, 'razorpay_payment_id': pid,
                                                  'razorpay_signature': sig(oid, pid)}, headers=auth(t))
    assert r.json['response']['payment']['status'] == 'FAILED'


def test_gateway_amount_mismatch_rejected(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    oid = start(c, t, card_id).json['response']['checkout']['order_id']
    pid = gw.pay(oid, amount=100)
    r = c.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid, 'razorpay_payment_id': pid,
                                                  'razorpay_signature': sig(oid, pid)}, headers=auth(t))
    assert r.status_code == 400 and PaymentTransactions.query.first().status == 'CREATED'


def test_other_user_cannot_verify_or_view_my_payment(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    body = start(c, t, card_id).json['response']
    oid, payment_id = body['checkout']['order_id'], body['payment']['payment_id']
    pid = gw.pay(oid)
    c2, t2 = login(app, sent_otps, mobile='9123456780')
    r = c2.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid, 'razorpay_payment_id': pid,
                                                   'razorpay_signature': sig(oid, pid)}, headers=auth(t2))
    assert r.status_code == 404
    assert c2.get(f'/v1/bills/payments/{payment_id}', headers=auth(t2)).status_code == 404
    assert start(c2, t2, card_id).status_code == 404


def test_webhook_signature_and_capture(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    oid = start(c, t, card_id).json['response']['checkout']['order_id']
    pid = gw.pay(oid)
    payload = json.dumps({'event': 'payment.captured',
                          'payload': {'payment': {'entity': gw.payments[pid]}}}).encode()
    assert c.post('/v1/bills/webhook', data=payload, content_type='application/json',
                  headers={'X-Razorpay-Signature': 'bad'}).status_code == 401
    good = hmac.new(b'test_webhook_secret', payload, hashlib.sha256).hexdigest()
    r = c.post('/v1/bills/webhook', data=payload, content_type='application/json',
               headers={'X-Razorpay-Signature': good})
    assert r.status_code == 200
    p = PaymentTransactions.query.first()
    assert p.status == 'SUCCESS' and p.verified_via == 'WEBHOOK'


def test_status_poll_reconciles_with_gateway(app, sent_otps, gw):
    c, t, card_id = setup_card(app, sent_otps)
    body = start(c, t, card_id).json['response']
    gw.pay(body['checkout']['order_id'])          # paid, but browser never called verify
    r = c.get(f"/v1/bills/payments/{body['payment']['payment_id']}", headers=auth(t))
    assert r.json['response']['payment']['status'] == 'SUCCESS'
    assert r.json['response']['payment']['verified_via'] == 'RECONCILE'
    hist = c.get('/v1/bills/payments', headers=auth(t)).json['response']
    assert hist['total'] == 1
