from datetime import timedelta

from portal import db
from portal.models.base import utcnow
from portal.models.otp_verifications import OTPVerifications
from portal.models.user_sessions import UserSessions

from .conftest import H, auth, login, new_client


def test_otp_rejects_invalid_mobile(app, sent_otps):
    r = new_client(app).post('/v1/authentication/otp/send', json={'mobile_number': '12345'})
    assert r.status_code == 400 and r.json['response']['code'] == 'VALIDATION_ERROR'


def test_otp_unavailable_when_sms_not_configured(app):
    app.config['SMS_PROVIDER'] = ''
    try:
        r = new_client(app).post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
        assert r.status_code == 503 and r.json['response']['code'] == 'OTP_PROVIDER_NOT_CONFIGURED'
    finally:
        app.config['SMS_PROVIDER'] = 'console'


def test_otp_is_random_hashed_and_not_returned(app, sent_otps):
    r = new_client(app).post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
    code = sent_otps['+919876543210']
    assert code not in r.get_data(as_text=True)
    row = OTPVerifications.query.first()
    assert code not in row.otp_hash and row.otp_hash.startswith(('scrypt:', 'pbkdf2:'))


def test_register_then_login_same_account(app, sent_otps):
    c = new_client(app)
    c.post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
    r = c.post('/v1/authentication/otp/verify', json={'mobile_number': '9876543210',
                                                       'otp_code': sent_otps['+919876543210']})
    body = r.json['response']
    assert r.status_code == 200 and body['is_new_user'] and body['needs_pin']
    assert 'cv_refresh' in r.headers.get('Set-Cookie', '') and 'HttpOnly' in r.headers['Set-Cookie']
    uid = body['user']['user_id']

    OTPVerifications.query.update({'created_on': utcnow() - timedelta(minutes=5)})
    db.session.commit()
    c2 = new_client(app)
    c2.post('/v1/authentication/otp/send', json={'mobile_number': '+919876543210'})
    r = c2.post('/v1/authentication/otp/verify', json={'mobile_number': '9876543210',
                                                        'otp_code': sent_otps['+919876543210']})
    assert r.json['response']['is_new_user'] is False and r.json['response']['user']['user_id'] == uid


def test_wrong_otp_attempts_then_locked(app, sent_otps):
    c = new_client(app)
    c.post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
    real = sent_otps['+919876543210']
    wrong = '000000' if real != '000000' else '111111'
    for _ in range(5):
        r = c.post('/v1/authentication/otp/verify', json={'mobile_number': '9876543210', 'otp_code': wrong})
        assert r.status_code == 400
    r = c.post('/v1/authentication/otp/verify', json={'mobile_number': '9876543210', 'otp_code': real})
    assert r.status_code == 400 and r.json['response']['code'] == 'OTP_NOT_FOUND'


def test_expired_otp(app, sent_otps):
    c = new_client(app)
    c.post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
    OTPVerifications.query.update({'expires_at': utcnow() - timedelta(seconds=1)})
    db.session.commit()
    r = c.post('/v1/authentication/otp/verify', json={'mobile_number': '9876543210',
                                                       'otp_code': sent_otps['+919876543210']})
    assert r.json['response']['code'] == 'OTP_EXPIRED'


def test_otp_resend_cooldown(app, sent_otps):
    c = new_client(app)
    c.post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
    r = c.post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
    assert r.status_code == 429 and r.json['response']['code'] == 'OTP_COOLDOWN'


def test_protected_routes_require_token(app):
    c = new_client(app)
    for path in ('/v1/authentication/me', '/v1/cards', '/v1/bills', '/v1/security/settings'):
        assert c.get(path).status_code == 401


def test_weak_pin_rejected(app, sent_otps):
    c, t = login(app, sent_otps, pin=None)
    r = c.post('/v1/security/pin', json={'new_pin': '1234'}, headers=auth(t))
    assert r.status_code == 400


def test_pin_change_requires_current_pin(app, sent_otps):
    c, t = login(app, sent_otps)
    assert c.post('/v1/security/pin', json={'new_pin': '5937'}, headers=auth(t)).status_code == 400
    assert c.post('/v1/security/pin', json={'current_pin': '4826', 'new_pin': '5937'},
                  headers=auth(t)).status_code == 200


def test_unlock_with_pin_and_csrf_header(app, sent_otps):
    c, _ = login(app, sent_otps)
    assert c.post('/v1/authentication/unlock', json={'pin': '4826'}).status_code == 403   # no header
    r = c.post('/v1/authentication/unlock', json={'pin': '4826'}, headers=H)
    assert r.status_code == 200 and r.json['response']['access_token']


def test_pin_lockout_revokes_sessions(app, sent_otps):
    c, _ = login(app, sent_otps)
    for i in range(4):
        r = c.post('/v1/authentication/unlock', json={'pin': '9999'}, headers=H)
        assert r.json['response']['code'] == 'PIN_INVALID'
    r = c.post('/v1/authentication/unlock', json={'pin': '9999'}, headers=H)
    assert r.json['response']['code'] == 'SESSION_ENDED'
    assert UserSessions.query.filter_by(status='ACTIVE').count() == 0


def test_idle_session_is_locked_server_side(app, sent_otps):
    c, t = login(app, sent_otps)
    UserSessions.query.update({'last_active_at': utcnow() - timedelta(minutes=30)})
    db.session.commit()
    assert c.get('/v1/cards', headers=auth(t)).json['response']['code'] == 'APP_LOCKED'
    assert c.post('/v1/authentication/refresh', headers=H).json['response']['code'] == 'APP_LOCKED'
    r = c.post('/v1/authentication/unlock', json={'pin': '4826'}, headers=H)
    assert c.get('/v1/cards', headers=auth(r.json['response']['access_token'])).status_code == 200


def test_refresh_rotates_and_detects_reuse(app, sent_otps):
    c, _ = login(app, sent_otps)
    old_cookie = c.get_cookie('cv_refresh', path='/v1/authentication').value
    assert c.post('/v1/authentication/refresh', headers=H).status_code == 200
    attacker = new_client(app)
    attacker.set_cookie('cv_refresh', old_cookie, path='/v1/authentication')
    assert attacker.post('/v1/authentication/refresh', headers=H).status_code == 401
    # Reuse of the rotated token revoked the whole session, including the legit device.
    assert c.post('/v1/authentication/refresh', headers=H).status_code == 401


def test_logout_revokes_session_and_access_token(app, sent_otps):
    c, t = login(app, sent_otps)
    assert c.post('/v1/authentication/logout', headers=H).status_code == 200
    assert c.get('/v1/authentication/me', headers=auth(t)).json['response']['code'] == 'SESSION_ENDED'
    assert c.get('/v1/authentication/session', headers=H).json['response']['has_session'] is False


def test_otp_returned_only_for_dev_console_provider(app, monkeypatch):
    def console_send(mobile, otp):
        return {'success': True, 'provider': 'console', 'message': 'ok'}
    monkeypatch.setattr('portal.routes.authentication.routes.send_otp_sms', console_send)
    r = new_client(app).post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
    assert len(r.json['response']['otp_number']) == 6          # dev convenience

    def real_sms(mobile, otp):
        return {'success': True, 'provider': 'msg91', 'message': 'ok'}
    monkeypatch.setattr('portal.routes.authentication.routes.send_otp_sms', real_sms)
    r = new_client(app).post('/v1/authentication/otp/send', json={'mobile_number': '9123456780'})
    assert 'otp_number' not in r.json['response']               # never with a real SMS provider


def test_returning_user_must_enter_pin_after_otp(app, sent_otps):
    from .conftest import login
    login(app, sent_otps)                                     # account now has a PIN
    OTPVerifications.query.update({'created_on': utcnow() - timedelta(minutes=5)})
    db.session.commit()
    c = new_client(app)
    c.post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'})
    r = c.post('/v1/authentication/otp/verify', json={'mobile_number': '9876543210',
                                                       'otp_code': sent_otps['+919876543210']})
    body = r.json['response']
    assert body['requires_unlock'] is True and 'access_token' not in body
    assert c.post('/v1/authentication/refresh', headers=H).json['response']['code'] == 'APP_LOCKED'
    assert c.post('/v1/authentication/unlock', json={'pin': '9999'}, headers=H).status_code == 401
    r = c.post('/v1/authentication/unlock', json={'pin': '4826'}, headers=H)
    assert r.status_code == 200 and r.json['response']['access_token']


def test_hourly_otp_limit_ignores_codes_that_were_used(app, sent_otps):
    from .conftest import login
    for _ in range(7):                                        # 7 successful sign-ins in an hour
        OTPVerifications.query.update({'created_on': utcnow() - timedelta(minutes=2)})
        db.session.commit()
        c = new_client(app)
        assert c.post('/v1/authentication/otp/send', json={'mobile_number': '9876543210'}).status_code == 200
        c.post('/v1/authentication/otp/verify', json={'mobile_number': '9876543210', 'otp_code': sent_otps['+919876543210']})
    # but 5 unused codes in an hour are still capped
    for i in range(6):
        OTPVerifications.query.update({'created_on': utcnow() - timedelta(minutes=2)})
        db.session.commit()
        r = new_client(app).post('/v1/authentication/otp/send', json={'mobile_number': '9123456780'})
    assert r.status_code == 429 and r.json['response']['code'] == 'OTP_LIMIT' and 'minute' in r.json['response']['message']
