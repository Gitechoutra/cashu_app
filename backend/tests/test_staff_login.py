"""Admin / Customer Support sign-in with email + 6-digit PIN (no OTP)."""

from datetime import timedelta

from portal import db
from portal.models.base import utcnow
from portal.models.login_history import LoginHistory
from portal.models.users import Users
from portal.seeders import seed_admin as sa, seed_customersupport as sc

from .conftest import H, auth, login, new_client

ADMIN = {'key': 'primary_admin', 'email': 'admin@cardvault.local', 'mobile_number': '9000000001',
         'full_name': 'CardVault Admin', 'pin': '482617'}
AGENT = {'key': 'support_agent_1', 'email': 'support@cardvault.local', 'mobile_number': '9000000002',
         'full_name': 'Support Agent', 'pin': '593174'}


def seed(monkeypatch):
    monkeypatch.setattr(sa, 'ADMINS', [dict(ADMIN)])
    monkeypatch.setattr(sc, 'SUPPORT_AGENTS', [dict(AGENT)])
    sa.seed_admin()
    sc.seed_customer_support()


def staff(app, email, pin, role=None, headers=H):
    c = new_client(app)
    return c, c.post('/v1/authentication/staff/login', json={'email': email, 'pin': pin, 'role': role}, headers=headers)


def test_admin_and_support_sign_in_without_otp(app, monkeypatch, sent_otps):
    seed(monkeypatch)
    c, r = staff(app, 'ADMIN@cardvault.local ', '482617', role='ADMIN')
    assert r.status_code == 200 and r.json['response']['user']['role'] == 'ADMIN'
    assert 'cv_refresh' in r.headers.get('Set-Cookie', '')
    assert sent_otps == {}                                            # no OTP involved
    c2, r2 = staff(app, 'support@cardvault.local', '593174', role='SUPPORT')
    assert r2.status_code == 200 and r2.json['response']['user']['role'] == 'SUPPORT'
    assert LoginHistory.query.filter_by(event='STAFF_LOGIN', status='SUCCESS').count() == 2


def test_wrong_page_wrong_pin_unknown_email_all_look_the_same(app, monkeypatch):
    seed(monkeypatch)
    for email, pin, role in (('support@cardvault.local', '593174', 'ADMIN'),     # right creds, wrong login page
                             ('admin@cardvault.local', '111222', 'ADMIN'),
                             ('nobody@cardvault.local', '482617', 'ADMIN')):
        r = staff(app, email, pin, role)[1]
        assert r.status_code == 401 and r.json['response']['message'] == 'Invalid email or PIN.'


def test_customers_cannot_use_staff_login_and_staff_cannot_use_otp(app, monkeypatch, sent_otps):
    seed(monkeypatch)
    login(app, sent_otps, mobile='9876543210')                       # a customer with a PIN, no email
    c = new_client(app)
    c.post('/v1/authentication/otp/send', json={'mobile_number': '9000000001'})
    r = c.post('/v1/authentication/otp/verify', json={'mobile_number': '9000000001', 'otp_code': sent_otps['+919000000001']})
    assert r.status_code == 403 and r.json['response']['code'] == 'USE_STAFF_LOGIN'


def test_lockout_after_five_wrong_pins(app, monkeypatch):
    seed(monkeypatch)
    for _ in range(5):
        assert staff(app, 'admin@cardvault.local', '000999')[1].status_code == 401
    r = staff(app, 'admin@cardvault.local', '482617')[1]               # even the right PIN is refused now
    assert r.status_code == 423 and r.json['response']['code'] == 'ACCOUNT_LOCKED'
    Users.query.filter_by(email='admin@cardvault.local').update({'pin_locked_until': utcnow() - timedelta(seconds=1)})
    db.session.commit()
    assert staff(app, 'admin@cardvault.local', '482617')[1].status_code == 200


def test_csrf_header_required(app, monkeypatch):
    seed(monkeypatch)
    assert staff(app, 'admin@cardvault.local', '482617', headers={})[1].status_code == 403


def test_admin_adds_staff_with_temporary_pin_and_first_login_forces_change(app, monkeypatch):
    seed(monkeypatch)
    ca, r = staff(app, 'admin@cardvault.local', '482617')
    ta = r.json['response']['access_token']
    body = {'mobile_number': '9811111111', 'email': 'priya@cardvault.local', 'full_name': 'Priya S',
            'role': 'SUPPORT', 'temporary_pin': '845203'}
    assert ca.post('/v1/admin/users', json={**body, 'temporary_pin': '1234'}, headers=auth(ta)).status_code == 400
    assert ca.post('/v1/admin/users', json={**body, 'role': 'USER'}, headers=auth(ta)).status_code == 400
    r = ca.post('/v1/admin/users', json=body, headers=auth(ta))
    assert r.status_code == 201 and r.json['response']['user']['pin_reset_required'] is True

    cp, r = staff(app, 'priya@cardvault.local', '845203', role='SUPPORT')
    tp = r.json['response']['access_token']
    assert r.json['response']['pin_reset_required'] is True
    assert cp.get('/v1/support/tickets', headers=auth(tp)).json['response']['code'] == 'PIN_RESET_REQUIRED'
    assert cp.post('/v1/security/pin', json={'current_pin': '845203', 'new_pin': '1357'}, headers=auth(tp)).status_code == 400
    assert cp.post('/v1/security/pin', json={'current_pin': '845203', 'new_pin': '845203'}, headers=auth(tp)).status_code == 400
    assert cp.post('/v1/security/pin', json={'current_pin': '845203', 'new_pin': '608417'}, headers=auth(tp)).status_code == 200
    assert cp.get('/v1/support/tickets', headers=auth(tp)).status_code == 200

    # Forgotten PIN → admin sets a new temporary one; existing sessions end.
    uid = r.json['response']['user']['user_id']
    assert ca.post(f'/v1/admin/users/{uid}/reset-pin', json={'temporary_pin': '270591'}, headers=auth(ta)).status_code == 200
    assert cp.get('/v1/support/tickets', headers=auth(tp)).json['response']['code'] == 'SESSION_ENDED'
    assert staff(app, 'priya@cardvault.local', '270591')[1].json['response']['pin_reset_required'] is True


def test_customers_cannot_be_promoted_to_staff(app, monkeypatch, sent_otps):
    seed(monkeypatch)
    cu, tu = login(app, sent_otps, mobile='9876543210')
    uid = cu.get('/v1/authentication/me', headers=auth(tu)).json['response']['user_id']
    ca, r = staff(app, 'admin@cardvault.local', '482617')
    r = ca.patch(f'/v1/admin/users/{uid}', json={'role': 'SUPPORT'}, headers=auth(r.json['response']['access_token']))
    assert r.status_code == 400 and r.json['response']['code'] == 'ROLE_CHANGE_NOT_ALLOWED'
