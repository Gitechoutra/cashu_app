"""Profiles, security preferences, login history, devices, notifications, platform
settings, reconciliation / payment exceptions, Scan & Pay history, bank accounts, KYC."""

import hashlib
import hmac
import json
from datetime import date, timedelta

from portal import db
from portal.models.bank_accounts import BankAccounts
from portal.models.login_history import LoginHistory
from portal.models.notifications import Notifications
from portal.models.reconciliation import Reconciliation
from portal.models.roles import Roles
from portal.models.transaction_errors import TransactionErrors
from portal.models.user_sessions import UserSessions
from portal.models.users import Users
from portal.models.base import utcnow

from .conftest import H, auth, idem, login, manual_card, new_client
from .test_bills import FakeRazorpay, sig  # noqa: F401  (fixture helpers)

DEV_A = {'X-Device-Id': 'device-aaaaaaaaaaaaaaaa'}
DEV_B = {'X-Device-Id': 'device-bbbbbbbbbbbbbbbb'}


def otp_login(app, sent_otps, mobile='9876543210', headers=None):
    # Age earlier OTPs so the 30-second resend cooldown doesn't block repeat sign-ins in tests.
    from portal.models.otp_verifications import OTPVerifications
    OTPVerifications.query.update({'created_on': utcnow() - timedelta(minutes=2)})
    db.session.commit()
    c = new_client(app)
    c.post('/v1/authentication/otp/send', json={'mobile_number': mobile})
    r = c.post('/v1/authentication/otp/verify', json={'mobile_number': mobile, 'otp_code': sent_otps['+91' + mobile]},
               headers=headers or {})
    if r.json['response'].get('requires_unlock'):          # returning user: OTP, then PIN
        r = c.post('/v1/authentication/unlock', json={'pin': '4826'}, headers={**H, **(headers or {})})
    return c, r.json['response']['access_token']


def make_admin(app, sent_otps, mobile='9000000001'):
    c, t = login(app, sent_otps, mobile=mobile, name='Admin User')
    Users.query.filter_by(mobile_number='+91' + mobile).update({'role_id': Roles.id_for('ADMIN')})
    db.session.commit()
    return c, t


# ── login history & devices ─────────────────────────────────────────────────

def test_login_history_records_success_and_failures(app, sent_otps):
    c, t = login(app, sent_otps)
    c.post('/v1/authentication/unlock', json={'pin': '9999'}, headers=H)
    c.post('/v1/authentication/unlock', json={'pin': '4826'}, headers=H)
    events = [(h.event, h.status) for h in LoginHistory.query.order_by(LoginHistory.login_id)]
    assert ('OTP_LOGIN', 'SUCCESS') in events and ('PIN_UNLOCK', 'FAILED') in events and ('PIN_UNLOCK', 'SUCCESS') in events
    hist = c.get('/v1/account/login-history', headers=auth(t)).json['response']
    assert hist['total'] == len(events) and 'pin' not in json.dumps(hist).replace('PIN_UNLOCK', '').replace('wrong_pin', '')


def test_new_device_alert_and_device_removal(app, sent_otps):
    login(app, sent_otps)                                                     # first device (no header) – registers
    ca, ta = otp_login(app, sent_otps, headers=DEV_A)
    assert Notifications.query.filter_by(type='SECURITY').count() == 1         # existing account, new device
    otp_login_again = otp_login(app, sent_otps, headers=DEV_A)                 # same device again → no new alert
    assert Notifications.query.filter_by(type='SECURITY').count() == 1
    cb, tb = otp_login(app, sent_otps, headers=DEV_B)
    devices = cb.get('/v1/account/devices', headers=auth(tb)).json['response']['devices']
    other = next(d for d in devices if not d['current'])
    current = next(d for d in devices if d['current'])
    assert cb.delete(f"/v1/account/devices/{current['device_id']}", headers=auth(tb)).status_code == 400
    assert cb.delete(f"/v1/account/devices/{other['device_id']}", headers=auth(tb)).status_code == 200
    assert ca.get('/v1/cards', headers=auth(ta)).json['response']['code'] == 'SESSION_ENDED'


def test_login_alerts_can_be_turned_off(app, sent_otps):
    c, t = login(app, sent_otps)
    c.patch('/v1/account/preferences', json={'login_alerts': False}, headers=auth(t))
    otp_login(app, sent_otps, headers=DEV_A)
    assert Notifications.query.filter_by(type='SECURITY').count() == 0


# ── preferences & profile ───────────────────────────────────────────────────

def test_personal_auto_lock_is_stricter_only(app, sent_otps):
    c, t = login(app, sent_otps)
    assert c.patch('/v1/account/preferences', json={'idle_lock_minutes': 60}, headers=auth(t)).status_code == 400
    r = c.patch('/v1/account/preferences', json={'idle_lock_minutes': 2}, headers=auth(t))
    assert r.status_code == 200 and r.json['response']['idle_lock_minutes'] == 2
    UserSessions.query.update({'last_active_at': utcnow() - timedelta(minutes=3)})
    db.session.commit()
    assert c.get('/v1/cards', headers=auth(t)).json['response']['code'] == 'APP_LOCKED'


def test_profile_update_and_validation(app, sent_otps):
    c, t = login(app, sent_otps)
    assert c.patch('/v1/account/profile', json={'email': 'not-an-email'}, headers=auth(t)).status_code == 400
    r = c.patch('/v1/account/profile', json={'email': 'Asha@Example.com', 'city': 'Vizag', 'preferred_language': 'te'},
                headers=auth(t)).json['response']
    assert r['email'] == 'asha@example.com' and r['email_verified'] is False and r['preferred_language'] == 'te'


# ── notifications ───────────────────────────────────────────────────────────

def test_due_reminders_generated_once_and_mark_read(app, sent_otps):
    c, t = login(app, sent_otps)
    manual_card(c, t, due_date=(date.today() + timedelta(days=2)).isoformat())
    r1 = c.get('/v1/notifications', headers=auth(t)).json['response']
    r2 = c.get('/v1/notifications', headers=auth(t)).json['response']
    due = [n for n in r2['items'] if n['type'] == 'BILL_DUE']
    assert len(due) == 1 and r1['unread'] == r2['unread']
    c.post('/v1/notifications/read', json={'all': True}, headers=auth(t))
    assert c.get('/v1/notifications/unread-count', headers=auth(t)).json['response']['unread'] == 0


def test_support_reply_notifies_customer(app, sent_otps):
    cu, tu = login(app, sent_otps)
    tid = cu.post('/v1/tickets', json={'subject': 'Help please', 'category': 'OTHER', 'message': 'Hi'},
                  headers=auth(tu)).json['response']['ticket']['ticket_id']
    cs, ts = login(app, sent_otps, mobile='9123456780', name='Agent One')
    Users.query.filter_by(mobile_number='+919123456780').update({'role_id': Roles.id_for('SUPPORT')})
    db.session.commit()
    cs.post(f'/v1/support/tickets/{tid}/messages', json={'message': 'Internal', 'internal': True}, headers=auth(ts))
    assert Notifications.query.filter_by(type='SUPPORT').count() == 0        # internal notes don't notify
    cs.post(f'/v1/support/tickets/{tid}/messages', json={'message': 'We are on it'}, headers=auth(ts))
    assert Notifications.query.filter_by(type='SUPPORT').count() == 1


# ── payments: settings, reconciliation, exceptions, notifications ───────────

def _gw(monkeypatch):
    g = FakeRazorpay()
    for fn in ('create_order', 'fetch_payment', 'fetch_order_payments'):
        monkeypatch.setattr(f'portal.helpers.razorpay_helper.{fn}', getattr(g, fn))
    return g


def test_platform_settings_drive_payment_limits(app, sent_otps, monkeypatch):
    _gw(monkeypatch)
    ca, ta = make_admin(app, sent_otps)
    cu, tu = login(app, sent_otps, mobile='9876543210')
    card_id = manual_card(cu, tu).json['response']['card']['card_id']
    r = ca.patch('/v1/admin/platform-settings', json={'values': {'MAX_CARD_PAYMENT_INR': '1000'}}, headers=auth(ta))
    assert r.status_code == 200
    r = cu.post('/v1/bills/payment-session', json={'card_id': card_id, 'amount': '1500', 'idempotency_key': idem()}, headers=auth(tu))
    assert r.status_code == 400 and 'Maximum' in r.json['response']['message']
    bad = ca.patch('/v1/admin/platform-settings', json={'values': {'MIN_CARD_PAYMENT_INR': '5000'}}, headers=auth(ta))
    assert bad.status_code == 400
    assert ca.patch('/v1/admin/platform-settings', json={'values': {'MAX_CARD_PAYMENT_INR': '-1'}}, headers=auth(ta)).status_code == 400


def test_public_settings_only_expose_public_keys(app, sent_otps):
    ca, ta = make_admin(app, sent_otps)
    ca.patch('/v1/admin/platform-settings', json={'values': {'MAINTENANCE_MESSAGE': 'Down at 2am'}}, headers=auth(ta))
    pub = new_client(app).get('/v1/platform/settings').json['response']
    assert pub['MAINTENANCE_MESSAGE'] == 'Down at 2am' and 'MAX_CARD_PAYMENT_INR' not in pub


def test_reconciliation_rows_notifications_and_exceptions(app, sent_otps, monkeypatch):
    g = _gw(monkeypatch)
    cu, tu = login(app, sent_otps, mobile='9876543210')
    card_id = manual_card(cu, tu).json['response']['card']['card_id']
    s = cu.post('/v1/bills/payment-session', json={'card_id': card_id, 'amount': '500', 'idempotency_key': idem()},
                headers=auth(tu)).json['response']
    oid = s['checkout']['order_id']
    # Forged signature → exception recorded, status unchanged
    cu.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid, 'razorpay_payment_id': 'pay_x',
                                              'razorpay_signature': 'bad'}, headers=auth(tu))
    assert TransactionErrors.query.filter_by(error_code='BAD_SIGNATURE').count() == 1
    # Real capture → reconciliation UPDATED + success notification
    pid = g.pay(oid)
    cu.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid, 'razorpay_payment_id': pid,
                                              'razorpay_signature': sig(oid, pid)}, headers=auth(tu))
    rec = Reconciliation.query.filter_by(result='UPDATED').one()
    assert rec.status_before == 'CREATED' and rec.status_after == 'SUCCESS' and rec.source == 'API_FETCH'
    assert Notifications.query.filter_by(type='PAYMENT').count() == 1

    # Mismatched gateway amount on a second payment → exception + MISMATCH row
    s2 = cu.post('/v1/bills/payment-session', json={'card_id': card_id, 'amount': '600', 'idempotency_key': idem()},
                 headers=auth(tu)).json['response']
    oid2 = s2['checkout']['order_id']
    pid2 = g.pay(oid2, amount=1)
    cu.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid2, 'razorpay_payment_id': pid2,
                                              'razorpay_signature': sig(oid2, pid2)}, headers=auth(tu))
    assert TransactionErrors.query.filter_by(error_code='GATEWAY_DATA_MISMATCH').count() == 1
    assert Reconciliation.query.filter_by(result='MISMATCH').count() == 1

    ca, ta = make_admin(app, sent_otps)
    errs = ca.get('/v1/admin/transaction-errors', headers=auth(ta)).json['response']
    assert errs['unresolved'] == 2
    assert ca.post(f"/v1/admin/transaction-errors/{errs['items'][0]['error_id']}/resolve", headers=auth(ta)).status_code == 200
    assert ca.get('/v1/admin/reconciliation', headers=auth(ta)).json['response']['total'] >= 2


def test_payment_alerts_off_suppresses_notification(app, sent_otps, monkeypatch):
    g = _gw(monkeypatch)
    cu, tu = login(app, sent_otps)
    cu.patch('/v1/account/preferences', json={'payment_alerts': False}, headers=auth(tu))
    card_id = manual_card(cu, tu).json['response']['card']['card_id']
    oid = cu.post('/v1/bills/payment-session', json={'card_id': card_id, 'amount': '500', 'idempotency_key': idem()},
                  headers=auth(tu)).json['response']['checkout']['order_id']
    pid = g.pay(oid)
    cu.post('/v1/bills/payment-verify', json={'razorpay_order_id': oid, 'razorpay_payment_id': pid,
                                              'razorpay_signature': sig(oid, pid)}, headers=auth(tu))
    assert Notifications.query.filter_by(type='PAYMENT').count() == 0


def test_admin_reconcile_run_updates_open_payments(app, sent_otps, monkeypatch):
    g = _gw(monkeypatch)
    cu, tu = login(app, sent_otps)
    card_id = manual_card(cu, tu).json['response']['card']['card_id']
    oid = cu.post('/v1/bills/payment-session', json={'card_id': card_id, 'amount': '500', 'idempotency_key': idem()},
                  headers=auth(tu)).json['response']['checkout']['order_id']
    g.pay(oid)                                        # paid, but the browser never verified
    ca, ta = make_admin(app, sent_otps)
    r = ca.post('/v1/admin/reconcile', headers=auth(ta)).json['response']
    assert r == {'checked': 1, 'updated': 1, 'errors': 0}


# ── card networks, Scan & Pay, bank accounts, KYC ───────────────────────────

def test_card_networks_from_table(app, sent_otps):
    c, t = login(app, sent_otps)
    codes = [n['code'] for n in c.get('/v1/cards/networks', headers=auth(t)).json['response']['networks']]
    assert codes[:3] == ['VISA', 'MASTERCARD', 'RUPAY'] and codes[-1] == 'OTHER'
    assert manual_card(c, t, card_network='DISCOVERX').status_code == 400


def test_scan_history(app, sent_otps):
    c, t = login(app, sent_otps)
    assert c.post('/v1/scan/payments', json={'payee_vpa': 'bad'}, headers=auth(t)).status_code == 400
    r = c.post('/v1/scan/payments', json={'payee_vpa': 'shop.one@okaxis', 'payee_name': '<b>Shop</b> One',
                                          'merchant_code': '5411', 'amount': '250.50'}, headers=auth(t))
    assert r.status_code == 201 and r.json['response']['payment']['status'] == 'HANDED_OFF'
    rows = c.get('/v1/scan/payments', headers=auth(t)).json['response']['payments']
    assert rows[0]['payee_vpa'] == 'shop.one@okaxis' and rows[0]['is_merchant'] is True


def test_bank_accounts_encrypted_masked_and_owned(app, sent_otps):
    c, t = login(app, sent_otps)
    body = {'account_holder_name': 'Asha Rao', 'bank_name': 'HDFC Bank', 'ifsc': 'hdfc0001234',
            'account_number': '50100123456789', 'confirm_account_number': '50100123456789'}
    assert c.post('/v1/account/bank-accounts', json={**body, 'ifsc': 'BAD'}, headers=auth(t)).status_code == 400
    assert c.post('/v1/account/bank-accounts', json={**body, 'confirm_account_number': '1'}, headers=auth(t)).status_code == 400
    r = c.post('/v1/account/bank-accounts', json=body, headers=auth(t))
    acc = r.json['response']['bank_account']
    assert r.status_code == 201 and acc['masked_account'].endswith('6789') and acc['is_primary']
    assert acc['verification_status'] == 'UNVERIFIED' and '50100123456789' not in json.dumps(r.json)
    row = BankAccounts.query.one()
    assert '50100123456789' not in row.account_number_encrypted
    assert c.post('/v1/account/bank-accounts', json=body, headers=auth(t)).status_code == 409
    c2, t2 = login(app, sent_otps, mobile='9123456780')
    assert c2.delete(f"/v1/account/bank-accounts/{acc['bank_account_id']}", headers=auth(t2)).status_code == 404
    assert c.delete(f"/v1/account/bank-accounts/{acc['bank_account_id']}", headers=auth(t)).status_code == 200


def test_kyc_status_and_staff_cannot_use_customer_tools(app, sent_otps):
    c, t = login(app, sent_otps)
    k = c.get('/v1/account/kyc', headers=auth(t)).json['response']
    assert k['status'] == 'NOT_STARTED' and k['provider_configured'] is False
    ca, ta = make_admin(app, sent_otps)
    assert ca.get('/v1/account/kyc', headers=auth(ta)).status_code == 403
    assert ca.post('/v1/scan/payments', json={'payee_vpa': 'a.b@ok'}, headers=auth(ta)).status_code == 403
    users = ca.get('/v1/admin/users', headers=auth(ta)).json['response']['items']
    assert all('kyc_status' in u for u in users)
