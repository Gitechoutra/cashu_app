"""
Mobile-number registration/login with SMS OTP, session refresh, app unlock
(PIN or biometric) and logout.

Flow:  /otp/send → /otp/verify (creates the account on first login, starts a
session, sets the refresh cookie) → onboarding sets name + PIN (security ns).
On every app open the SPA calls /session and then /unlock (PIN) or
/webauthn/verify (biometric) to obtain an access token.
"""

import secrets
from datetime import timedelta

from flask import current_app, request
from flask_restx import Resource
from werkzeug.security import check_password_hash, generate_password_hash

from portal import db
from portal.extensions import limiter
from portal.helpers import webauthn_helper
from portal.helpers.audit import audit
from portal.helpers.activity import bind_device, log_login, notify
from portal.models.login_history import LoginEvent, LoginStatus
from portal.models.notifications import NotificationType
from portal.helpers.auth import (
    auth_required, clear_refresh_cookie, create_session, current_user, is_locked,
    issue_access_token, revoke_session, rotate_refresh, session_from_cookie, set_refresh_cookie,
)
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.sms import send_otp_sms, sms_configured
from portal.helpers.validators import Validator, normalize_mobile, validate_name, validate_otp
from portal.models.base import iso, utcnow
from portal.models.otp_verifications import OTPVerifications, OTPPurpose, OTPStatus
from portal.models.user_sessions import UserSessions, SessionStatus
from portal.models.roles import Roles, RoleName
from portal.models.users import Users, UserStatus
from portal.models.webauthn_credentials import WebAuthnCredentials

from . import ns, logger


def _json():
    return request.get_json(silent=True) or {}


def user_payload(user):
    return {
        'user_id': user.public_id,
        'full_name': user.full_name,
        'mobile_number': user.masked_mobile,
        'role': user.role_name,
        'email': user.email if user.role_name in RoleName.STAFF else None,
        'pin_reset_required': bool(user.pin_reset_required),
        'role_display': user.role.display_name if user.role else None,
        'has_pin': bool(user.pin_hash),
        'seed_managed': bool(user.seed_key),
        'biometric_enabled': user.webauthn_credentials.count() > 0,
        'created_on': iso(user.created_on),
    }


def _session_response(user, session, raw_refresh, extra=None, status=200):
    body = {'access_token': issue_access_token(user, session),
            'expires_in': int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds()),
            'user': user_payload(user)}
    body.update(extra or {})
    resp = ok(body, status)
    set_refresh_cookie(resp, raw_refresh)
    return resp


# ── OTP: send ───────────────────────────────────────────────────────────────

@ns.route('/otp/send')
class SendOTP(Resource):
    @ns.doc(description='Send a 6-digit login/registration OTP to an Indian mobile number.')
    @limiter.limit('5 per minute')
    def post(self):
        try:
            mobile, err = normalize_mobile(_json().get('mobile_number'))
            if err:
                return fail(err, 400, code='VALIDATION_ERROR', errors={'mobile_number': err})
            if not sms_configured():
                return fail('OTP login is not available: SMS provider not configured.', 503,
                            code='OTP_PROVIDER_NOT_CONFIGURED')

            cfg = current_app.config
            now = utcnow()
            last = (OTPVerifications.query.filter_by(mobile_number=mobile)
                    .order_by(OTPVerifications.created_on.desc()).first())
            if last and (now - last.created_on).total_seconds() < cfg['OTP_RESEND_COOLDOWN_SECONDS']:
                wait = cfg['OTP_RESEND_COOLDOWN_SECONDS'] - int((now - last.created_on).total_seconds())
                return fail(f'Please wait {wait}s before requesting another OTP.', 429,
                            code='OTP_COOLDOWN', retry_after=wait)
            # Hourly limit: only codes that were requested but never used count (a normal sign-in uses its
            # code), so regular logins aren't blocked while code-spamming still is. Plus an absolute ceiling.
            hour_ago = now - timedelta(hours=1)
            recent = OTPVerifications.query.filter(OTPVerifications.mobile_number == mobile,
                                                   OTPVerifications.created_on >= hour_ago)
            unused = recent.filter(OTPVerifications.status != OTPStatus.VERIFIED)
            if unused.count() >= cfg['OTP_MAX_PER_HOUR'] or recent.count() >= cfg['OTP_ABSOLUTE_MAX_PER_HOUR']:
                oldest = unused.order_by(OTPVerifications.created_on.asc()).first() or                     recent.order_by(OTPVerifications.created_on.asc()).first()
                mins = max(1, int((oldest.created_on + timedelta(hours=1) - now).total_seconds() // 60) + 1)
                return fail(f'Too many OTP requests for this number. Try again in {mins} minute(s).', 429,
                            code='OTP_LIMIT', retry_after=mins * 60)

            OTPVerifications.query.filter_by(mobile_number=mobile, status=OTPStatus.PENDING) \
                .update({'status': OTPStatus.SUPERSEDED})
            code = f'{secrets.randbelow(10 ** cfg["OTP_LENGTH"]):0{cfg["OTP_LENGTH"]}d}'
            otp = OTPVerifications(
                mobile_number=mobile, otp_hash=generate_password_hash(code), purpose=OTPPurpose.LOGIN,
                max_attempts=cfg['OTP_MAX_ATTEMPTS'], expires_at=now + timedelta(seconds=cfg['OTP_TTL_SECONDS']),
                ip_address=(request.remote_addr or '')[:64])
            db.session.add(otp)
            db.session.commit()

            result = send_otp_sms(mobile, code)
            if not result['success']:
                otp.status = OTPStatus.FAILED
                db.session.commit()
                return fail('Could not send the OTP. Please try again.', 502, code='OTP_SEND_FAILED')

            body = {'message': 'OTP sent.', 'mobile_number': mobile[:3] + ' ••••• ' + mobile[-4:],
                    'expires_in': cfg['OTP_TTL_SECONDS'],
                    'resend_after': cfg['OTP_RESEND_COOLDOWN_SECONDS'],
                    'dev_console_otp': result['provider'] == 'console'}
            # Development only: with the console SMS provider (refused when APP_ENV=PROD) the OTP is
            # returned so the sign-in screen can show it. With a real SMS provider it is NEVER returned —
            # otherwise anyone could sign in to any account just by knowing its mobile number.
            if result['provider'] == 'console' and cfg['APP_ENV'] != 'PROD':
                body['otp_number'] = code
            return ok(body)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'otp/send')


# ── OTP: verify → login / register ──────────────────────────────────────────

@ns.route('/otp/verify')
class VerifyOTP(Resource):
    @ns.doc(description='Verify the OTP. Creates the account on first login, starts a session '
                        '(refresh token in an httpOnly cookie) and returns an access token.')
    @limiter.limit('10 per minute')
    def post(self):
        try:
            body = _json()
            v = Validator()
            mobile, e1 = normalize_mobile(body.get('mobile_number'))
            code, e2 = validate_otp(body.get('otp_code'))
            v.check('mobile_number', e1)
            v.check('otp_code', e2)
            if not v.ok:
                return v.response()

            otp = (OTPVerifications.query.filter_by(mobile_number=mobile, status=OTPStatus.PENDING)
                   .order_by(OTPVerifications.created_on.desc()).first())
            if not otp:
                return fail('No active OTP. Please request a new one.', 400, code='OTP_NOT_FOUND')
            if utcnow() > otp.expires_at:
                otp.status = OTPStatus.EXPIRED
                db.session.commit()
                return fail('OTP expired. Please request a new one.', 400, code='OTP_EXPIRED')

            otp.attempts += 1
            if not check_password_hash(otp.otp_hash, code):
                existing = Users.query.filter_by(mobile_number=mobile).first()
                log_login(existing.user_id if existing else None, LoginEvent.OTP_LOGIN, LoginStatus.FAILED, 'wrong_otp')
                remaining = otp.max_attempts - otp.attempts
                if remaining <= 0:
                    otp.status = OTPStatus.FAILED
                db.session.commit()
                return fail('Incorrect OTP.' if remaining > 0 else 'Too many wrong attempts. Request a new OTP.',
                            400, code='OTP_INVALID', attempts_remaining=max(remaining, 0))

            otp.status = OTPStatus.VERIFIED
            otp.verified_at = utcnow()

            user = Users.query.filter_by(mobile_number=mobile).first()
            is_new = user is None
            if is_new:
                # Self sign-up always creates a customer. Staff roles are granted only by an Admin.
                user = Users(mobile_number=mobile, status=UserStatus.ACTIVE, role_id=Roles.id_for(RoleName.USER))
                db.session.add(user)
                db.session.flush()
            elif user.role_name in RoleName.STAFF:
                log_login(user.user_id, LoginEvent.OTP_LOGIN, LoginStatus.BLOCKED, 'staff_must_use_email_login')
                db.session.commit()
                return fail('Staff accounts sign in with email and PIN on the Admin / Customer Support login page.',
                            403, code='USE_STAFF_LOGIN')
            elif user.status != UserStatus.ACTIVE:
                log_login(user.user_id, LoginEvent.OTP_LOGIN, LoginStatus.BLOCKED, 'account_suspended')
                db.session.commit()
                return fail('This account is suspended. Contact support.', 403, code='ACCOUNT_INACTIVE')

            user.last_login = utcnow()
            session, raw = create_session(user)
            device, new_device = bind_device(user)
            if device is not None:
                session.device_binding_id = device.device_binding_id
            log_login(user.user_id, LoginEvent.OTP_LOGIN, LoginStatus.SUCCESS, session=session, device=device)
            # Alert only when an existing account appears on a device it hasn't used before.
            if new_device and not is_new:
                notify(user.user_id, NotificationType.SECURITY, 'New device signed in',
                       f"{device.device_name} signed in to your account. If this wasn't you, "
                       'sign it out from Settings and contact support.', link='/user/settings')
            requires_pin = bool(user.pin_hash)
            if requires_pin:
                # OTP proves the phone; the PIN proves the person. The session stays locked (refused by
                # every API) until /authentication/unlock (PIN) or biometric unlock succeeds.
                session.last_active_at = utcnow() - timedelta(days=1)
            db.session.commit()
            audit('USER_REGISTERED' if is_new else 'USER_LOGIN', user.user_id, 'SESSION', session.public_id)

            if requires_pin:
                resp = ok({'requires_unlock': True, 'is_new_user': False,
                           'user': {'full_name': user.full_name, 'mobile_number': user.masked_mobile,
                                    'role': user.role_name, 'has_pin': True,
                                    'biometric_enabled': user.webauthn_credentials.count() > 0}})
                set_refresh_cookie(resp, raw)
                return resp

            return _session_response(user, session, raw, {
                'is_new_user': is_new,
                'needs_profile': not user.full_name,
                'needs_pin': not user.pin_hash,
            })
        except Exception:
            db.session.rollback()
            return server_error(logger, 'otp/verify')


# ── Session on this device ──────────────────────────────────────────────────

@ns.route('/session')
class DeviceSession(Resource):
    @ns.doc(description='Is there a signed-in session on this device (refresh cookie)? '
                        'Used on app open to decide between the lock screen and sign-in.')
    def get(self):
        session, err = session_from_cookie()
        if err:
            return ok({'has_session': False})
        u = session.user
        return ok({'has_session': True, 'locked': True, 'idle_locked': is_locked(session),
                   'user': {'full_name': u.full_name, 'mobile_number': u.masked_mobile, 'role': u.role_name,
                            'has_pin': bool(u.pin_hash),
                            'biometric_enabled': u.webauthn_credentials.count() > 0}})


@ns.route('/refresh')
class Refresh(Resource):
    @ns.doc(description='Silently renew the access token while the app is in use. '
                        'Refused once the session is idle-locked.')
    @limiter.limit('30 per minute')
    def post(self):
        try:
            session, err = session_from_cookie()
            if err:
                return err
            if is_locked(session):
                if not session.user.pin_hash:
                    revoke_session(session, 'IDLE_NO_PIN')
                    db.session.commit()
                    return fail('Session ended. Please sign in again.', 401, code='SESSION_ENDED')
                return fail('App locked. Unlock with your PIN.', 401, code='APP_LOCKED')
            raw = rotate_refresh(session)
            session.last_active_at = utcnow()
            db.session.commit()
            return _session_response(session.user, session, raw)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'refresh')


def _unlock_success(session, method):
    user = session.user
    user.pin_failed_attempts = 0
    log_login(user.user_id, LoginEvent.BIOMETRIC_UNLOCK if method == 'BIOMETRIC' else LoginEvent.PIN_UNLOCK,
              LoginStatus.SUCCESS, session=session)
    session.last_active_at = utcnow()
    raw = rotate_refresh(session)
    db.session.commit()
    audit('APP_UNLOCK', user.user_id, 'SESSION', session.public_id, details={'method': method})
    return _session_response(user, session, raw)


@ns.route('/unlock')
class UnlockWithPin(Resource):
    @ns.doc(description='Unlock the app on this device with the app PIN.')
    @limiter.limit('10 per minute')
    def post(self):
        try:
            session, err = session_from_cookie()
            if err:
                return err
            user = session.user
            if not user.pin_hash:
                return fail('No PIN set. Please sign in with OTP.', 400, code='PIN_NOT_SET')
            pin = str(_json().get('pin') or '')
            if check_password_hash(user.pin_hash, pin):
                return _unlock_success(session, 'PIN')

            user.pin_failed_attempts += 1
            remaining = current_app.config['PIN_MAX_ATTEMPTS'] - user.pin_failed_attempts
            log_login(user.user_id, LoginEvent.PIN_UNLOCK, LoginStatus.FAILED if remaining > 0 else LoginStatus.BLOCKED,
                      'wrong_pin' if remaining > 0 else 'pin_attempts_exceeded', session=session)
            if remaining <= 0:
                notify(user.user_id, NotificationType.SECURITY, 'Signed out after wrong PIN attempts',
                       'Too many incorrect PINs were entered, so every device was signed out.', link='/user/settings')
            if remaining <= 0:
                # Too many wrong PINs: end every session; the user must re-verify by OTP.
                for s in UserSessions.query.filter_by(user_id=user.user_id, status=SessionStatus.ACTIVE):
                    revoke_session(s, 'PIN_ATTEMPTS_EXCEEDED')
                user.pin_failed_attempts = 0
                db.session.commit()
                audit('PIN_LOCKOUT', user.user_id, status='FAILED')
                resp = fail('Too many wrong PIN attempts. Please sign in again with OTP.', 401,
                                  code='SESSION_ENDED')
                clear_refresh_cookie(resp)
                return resp
            db.session.commit()
            return fail('Incorrect PIN.', 401, code='PIN_INVALID', attempts_remaining=remaining)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'unlock')


@ns.route('/webauthn/options')
class BiometricUnlockOptions(Resource):
    @ns.doc(description='Get a WebAuthn challenge to unlock with fingerprint / Face ID.')
    @limiter.limit('20 per minute')
    def post(self):
        try:
            session, err = session_from_cookie()
            if err:
                return err
            creds = session.user.webauthn_credentials.all()
            if not creds:
                return fail('Biometric unlock is not set up on this account.', 400, code='BIOMETRIC_NOT_SET')
            opts = webauthn_helper.authentication_options(session, creds)
            db.session.commit()
            return ok({'options': opts})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'webauthn/options')


@ns.route('/webauthn/verify')
class BiometricUnlockVerify(Resource):
    @ns.doc(description='Verify the WebAuthn assertion and unlock.')
    @limiter.limit('20 per minute')
    def post(self):
        try:
            session, err = session_from_cookie()
            if err:
                return err
            credential = _json().get('credential') or {}
            stored = WebAuthnCredentials.query.filter_by(
                user_id=session.user_id, credential_id=str(credential.get('id', ''))[:512]).first()
            if not stored:
                webauthn_helper._pop_challenge(session)
                db.session.commit()
                return fail('This device key is not registered.', 401, code='BIOMETRIC_FAILED')
            try:
                stored.sign_count = webauthn_helper.verify_authentication(session, credential, stored)
            except Exception as e:
                log_login(session.user_id, LoginEvent.BIOMETRIC_UNLOCK, LoginStatus.FAILED, 'assertion_rejected', session=session)
                db.session.commit()          # challenge already consumed
                logger.info(f'[webauthn] assertion rejected: {e.__class__.__name__}')
                return fail('Biometric verification failed. Use your PIN.', 401, code='BIOMETRIC_FAILED')
            stored.last_used_on = utcnow()
            return _unlock_success(session, 'BIOMETRIC')
        except Exception:
            db.session.rollback()
            return server_error(logger, 'webauthn/verify')


@ns.route('/logout')
class Logout(Resource):
    @ns.doc(description='Sign out on this device: revokes the session and clears the cookie.')
    def post(self):
        try:
            session, err = session_from_cookie()
            if session:
                revoke_session(session, 'LOGOUT')
                log_login(session.user_id, LoginEvent.LOGOUT, LoginStatus.SUCCESS, session=session)
                db.session.commit()
                audit('USER_LOGOUT', session.user_id, 'SESSION', session.public_id)
            resp = ok({'message': 'Signed out.'})
            clear_refresh_cookie(resp)
            return resp
        except Exception:
            db.session.rollback()
            return server_error(logger, 'logout')


# ── Staff login: email + 6-digit PIN (Admin / Customer Support, no OTP) ─────

STAFF_LOCK_MINUTES = 15
STAFF_MAX_ATTEMPTS = 5
# Compared against when the email is unknown, so response time doesn't reveal which emails exist.
_DUMMY_PIN_HASH = generate_password_hash('000000-not-a-real-pin')


@ns.route('/staff/login')
class StaffLogin(Resource):
    @ns.doc(description='Admin / Customer Support sign-in with email + 6-digit PIN. '
                        'Optional "role" (ADMIN|SUPPORT) restricts which role may sign in on that page. '
                        f'{STAFF_MAX_ATTEMPTS} wrong PINs lock the account for {STAFF_LOCK_MINUTES} minutes.')
    @limiter.limit('10 per minute')
    def post(self):
        try:
            if request.headers.get('X-Requested-With') != 'cardvault':
                return fail('Missing request header.', 403, code='CSRF_CHECK_FAILED')
            body = _json()
            email = str(body.get('email') or '').strip().lower()[:254]
            pin = str(body.get('pin') or '')[:12]
            want = str(body.get('role') or '').upper()
            generic = fail('Invalid email or PIN.', 401, code='INVALID_CREDENTIALS')
            if not email or not pin:
                return fail('Enter your email and PIN.', 400, code='VALIDATION_ERROR')

            user = Users.query.filter_by(email=email).first() if email else None
            staff = user is not None and user.role_name in RoleName.STAFF and (want not in RoleName.STAFF or user.role_name == want)
            if not staff or not user.pin_hash:
                check_password_hash(_DUMMY_PIN_HASH, pin)            # equalise timing
                log_login(user.user_id if user else None, LoginEvent.STAFF_LOGIN, LoginStatus.FAILED, 'unknown_or_not_staff')
                db.session.commit()
                return generic

            now = utcnow()
            if user.pin_locked_until and user.pin_locked_until > now:
                mins = max(1, int((user.pin_locked_until - now).total_seconds() // 60) + 1)
                log_login(user.user_id, LoginEvent.STAFF_LOGIN, LoginStatus.BLOCKED, 'locked')
                db.session.commit()
                return fail(f'Too many wrong attempts. Try again in {mins} minute(s).', 423, code='ACCOUNT_LOCKED')

            if not check_password_hash(user.pin_hash, pin):
                user.pin_failed_attempts += 1
                if user.pin_failed_attempts >= STAFF_MAX_ATTEMPTS:
                    user.pin_failed_attempts = 0
                    user.pin_locked_until = now + timedelta(minutes=STAFF_LOCK_MINUTES)
                    log_login(user.user_id, LoginEvent.STAFF_LOGIN, LoginStatus.BLOCKED, 'pin_attempts_exceeded')
                    notify(user.user_id, NotificationType.SECURITY, 'Staff sign-in locked',
                           f'{STAFF_MAX_ATTEMPTS} wrong PINs were entered for your account. Sign-in is locked for '
                           f'{STAFF_LOCK_MINUTES} minutes.')
                    audit('STAFF_LOGIN_LOCKED', user.user_id, status='FAILED', commit=False)
                else:
                    log_login(user.user_id, LoginEvent.STAFF_LOGIN, LoginStatus.FAILED, 'wrong_pin')
                db.session.commit()
                return generic

            if user.status != UserStatus.ACTIVE:
                log_login(user.user_id, LoginEvent.STAFF_LOGIN, LoginStatus.BLOCKED, 'account_suspended')
                db.session.commit()
                return fail('This account is suspended.', 403, code='ACCOUNT_INACTIVE')

            seen_before = user.last_login is not None
            user.pin_failed_attempts, user.pin_locked_until, user.last_login = 0, None, now
            session, raw = create_session(user)
            device, new_device = bind_device(user)
            if device is not None:
                session.device_binding_id = device.device_binding_id
            log_login(user.user_id, LoginEvent.STAFF_LOGIN, LoginStatus.SUCCESS, session=session, device=device)
            if new_device and seen_before:
                notify(user.user_id, NotificationType.SECURITY, 'New device signed in',
                       f'{device.device_name} signed in to your staff account.')
            db.session.commit()
            audit('STAFF_LOGIN', user.user_id, 'SESSION', session.public_id)
            return _session_response(user, session, raw, {'needs_pin': False, 'needs_profile': not user.full_name,
                                                          'pin_reset_required': bool(user.pin_reset_required)})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'staff/login')


# ── Profile ─────────────────────────────────────────────────────────────────

@ns.route('/me')
class Me(Resource):
    @ns.doc(description='Current user profile.')
    @auth_required
    def get(self):
        return ok(user_payload(current_user()))

    @ns.doc(description='Update profile (full name).')
    @auth_required
    def patch(self):
        try:
            name, err = validate_name(_json().get('full_name'), required=True)
            if err:
                return fail(err, 400, code='VALIDATION_ERROR', errors={'full_name': err})
            user = current_user()
            from portal.seeders.staff_sync import managed_fields
            if 'full_name' in managed_fields(user):
                return fail('Your name is managed by the administrator in the seed file.', 403, code='MANAGED_BY_SEED')
            user.full_name = name
            db.session.commit()
            return ok(user_payload(user))
        except Exception:
            db.session.rollback()
            return server_error(logger, 'me/patch')
