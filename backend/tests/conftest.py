"""Test fixtures. Uses APP_ENV=TEST (SQLite in memory). The SMS sender and the
Razorpay HTTP calls are replaced with in-process fakes — no network is touched."""

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['APP_ENV'] = 'TEST'

from portal import InitApp, db  # noqa: E402

H = {'X-Requested-With': 'cardvault'}


@pytest.fixture(scope='session')
def app():
    return InitApp().app('TEST')


@pytest.fixture(autouse=True)
def _db(app, monkeypatch):
    # Tests start without the staff accounts from the seed files (see test_staff_seed.py).
    monkeypatch.setattr('portal.seeders.seed_admin.ADMINS', [])
    monkeypatch.setattr('portal.seeders.seed_customersupport.SUPPORT_AGENTS', [])
    with app.app_context():
        db.drop_all()
        db.create_all()
        from portal.seeders import run_all_seeders
        run_all_seeders()
        yield
        db.session.remove()
        from portal.providers.card_data import registry
        registry._override = None


@pytest.fixture
def sent_otps(monkeypatch):
    box = {}

    def fake_send(mobile, otp):
        box[mobile] = otp
        return {'success': True, 'provider': 'test', 'message': 'ok'}

    monkeypatch.setattr('portal.routes.authentication.routes.send_otp_sms', fake_send)
    return box


def new_client(app):
    return app.test_client()


def login(app, sent_otps, mobile='9876543210', pin='4826', name='Asha Rao'):
    """Full OTP sign-in (+ optional name and PIN). Returns (client, access_token)."""
    c = new_client(app)
    r = c.post('/v1/authentication/otp/send', json={'mobile_number': mobile})
    assert r.status_code == 200, r.json
    code = sent_otps['+91' + mobile[-10:]]
    r = c.post('/v1/authentication/otp/verify', json={'mobile_number': mobile, 'otp_code': code})
    assert r.status_code == 200, r.json
    token = r.json['response']['access_token']
    hdr = {'Authorization': f'Bearer {token}'}
    if name:
        c.patch('/v1/authentication/me', json={'full_name': name}, headers=hdr)
    if pin:
        assert c.post('/v1/security/pin', json={'new_pin': pin}, headers=hdr).status_code == 200
    return c, token


def auth(token):
    return {'Authorization': f'Bearer {token}'}


def issuer_id(client, token, code='HDFC'):
    r = client.get('/v1/cards/issuers', headers=auth(token))
    return next(i['issuer_id'] for i in r.json['response']['issuers'] if i['code'] == code)


def manual_card(client, token, **over):
    body = {'issuer_id': issuer_id(client, token), 'card_nickname': 'Regalia', 'card_network': 'VISA',
            'last_four_digits': '4242', 'credit_limit': '200000', 'outstanding_balance': '45000.50',
            'minimum_amount_due': '2250', 'billing_day': 12, 'due_date': _in_days(10)}
    body.update(over)
    return client.post('/v1/cards', json=body, headers=auth(token))


def _in_days(n):
    from datetime import date, timedelta
    return (date.today() + timedelta(days=n)).isoformat()


def idem():
    return uuid.uuid4().hex
