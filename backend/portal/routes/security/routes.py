"""App PIN, biometric (WebAuthn) enrolment and device-session management."""

from flask import current_app, g, request
from flask_restx import Resource
from werkzeug.security import check_password_hash, generate_password_hash

from portal import db
from portal.extensions import limiter
from portal.helpers import webauthn_helper
from portal.helpers.audit import audit
from portal.helpers.auth import auth_required, current_user, revoke_session
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.validators import clean_text, validate_pin, validate_staff_pin
from portal.models.roles import RoleName
from portal.models.base import iso, utcnow
from portal.models.user_sessions import UserSessions, SessionStatus
from portal.models.webauthn_credentials import WebAuthnCredentials

from . import ns, logger


def _json():
    return request.get_json(silent=True) or {}


@ns.route('/settings')
class SecuritySettings(Resource):
    @ns.doc(description='PIN status, enrolled biometric devices and active sessions.')
    @auth_required
    def get(self):
        user = current_user()
        sessions = (UserSessions.query.filter_by(user_id=user.user_id, status=SessionStatus.ACTIVE)
                    .filter(UserSessions.expires_at > utcnow())
                    .order_by(UserSessions.last_active_at.desc()).all())
        return ok({
            'has_pin': bool(user.pin_hash),
            'pin_set_at': iso(user.pin_set_at),
            'idle_lock_minutes': current_app.config['SESSION_IDLE_LOCK_MINUTES'],
            'biometrics': [{'id': c.credential_pk, 'label': c.label or 'This device',
                            'created_on': iso(c.created_on), 'last_used_on': iso(c.last_used_on)}
                           for c in user.webauthn_credentials.all()],
            'sessions': [{'session_id': s.public_id, 'current': s.session_id == g.session.session_id,
                          'user_agent': s.user_agent, 'created_on': iso(s.created_on),
                          'last_active_at': iso(s.last_active_at)} for s in sessions],
        })


@ns.route('/pin')
class AppPin(Resource):
    @ns.doc(description='Set the app PIN (first time) or change it (requires current_pin).')
    @limiter.limit('10 per minute')
    @auth_required
    def post(self):
        try:
            user = current_user()
            from portal.seeders.staff_sync import managed_fields
            if 'pin' in managed_fields(user):
                return fail("Your PIN is managed by the administrator in the seed file and can't be changed here.",
                            403, code='MANAGED_BY_SEED')
            body = _json()
            if user.pin_hash:
                if not check_password_hash(user.pin_hash, str(body.get('current_pin') or '')):
                    user.pin_failed_attempts += 1
                    db.session.commit()
                    audit('PIN_CHANGE', user.user_id, status='FAILED')
                    return fail('Current PIN is incorrect.', 400, code='PIN_INVALID',
                                errors={'current_pin': 'Current PIN is incorrect.'})
            staff = user.role_name in RoleName.STAFF
            pin, err = (validate_staff_pin if staff else validate_pin)(body.get('new_pin'))
            if not err and staff and user.pin_hash and check_password_hash(user.pin_hash, pin):
                err = 'Choose a PIN different from your current one.'
            if err:
                return fail(err, 400, code='VALIDATION_ERROR', errors={'new_pin': err})
            first_time = not user.pin_hash
            user.pin_hash = generate_password_hash(pin)
            user.pin_set_at = utcnow()
            user.pin_failed_attempts = 0
            user.pin_reset_required = False
            db.session.commit()
            audit('PIN_SET' if first_time else 'PIN_CHANGE', user.user_id)
            return ok({'message': 'PIN saved.', 'has_pin': True})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'pin')


@ns.route('/webauthn/register/options')
class BiometricRegisterOptions(Resource):
    @ns.doc(description='Begin fingerprint / Face ID enrolment on this device.')
    @auth_required
    def post(self):
        try:
            user = current_user()
            if not user.pin_hash:
                return fail('Set an app PIN before enabling biometrics.', 400, code='PIN_NOT_SET')
            opts = webauthn_helper.registration_options(user, g.session, user.webauthn_credentials.all())
            db.session.commit()
            return ok({'options': opts})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'webauthn/register/options')


@ns.route('/webauthn/register/verify')
class BiometricRegisterVerify(Resource):
    @ns.doc(description='Finish biometric enrolment.')
    @auth_required
    def post(self):
        try:
            user = current_user()
            body = _json()
            try:
                cred_id, pub, count = webauthn_helper.verify_registration(g.session, body.get('credential') or {})
            except Exception as e:
                db.session.commit()
                logger.info(f'[webauthn] registration rejected: {e.__class__.__name__}')
                return fail('Biometric setup could not be verified. Please try again.', 400,
                            code='BIOMETRIC_SETUP_FAILED')
            if WebAuthnCredentials.query.filter_by(credential_id=cred_id).first():
                return fail('This device is already enrolled.', 409, code='DUPLICATE')
            label = clean_text(body.get('label'))[:60] or 'This device'
            db.session.add(WebAuthnCredentials(user_id=user.user_id, credential_id=cred_id,
                                               public_key=pub, sign_count=count, label=label))
            db.session.commit()
            audit('BIOMETRIC_ENROLLED', user.user_id)
            return ok({'message': 'Biometric unlock enabled.'}, 201)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'webauthn/register/verify')


@ns.route('/webauthn/<int:credential_pk>')
class BiometricCredential(Resource):
    @ns.doc(description='Remove an enrolled biometric device.')
    @auth_required
    def delete(self, credential_pk):
        user = current_user()
        c = WebAuthnCredentials.query.filter_by(credential_pk=credential_pk, user_id=user.user_id).first()
        if not c:
            return fail('Not found.', 404, code='NOT_FOUND')
        db.session.delete(c)
        db.session.commit()
        audit('BIOMETRIC_REMOVED', user.user_id)
        return ok({'message': 'Biometric device removed.'})


@ns.route('/sessions/<string:session_id>')
class DeviceSessionRevoke(Resource):
    @ns.doc(description='Sign out another device.')
    @auth_required
    def delete(self, session_id):
        user = current_user()
        s = UserSessions.query.filter_by(public_id=session_id[:32], user_id=user.user_id,
                                         status=SessionStatus.ACTIVE).first()
        if not s:
            return fail('Session not found.', 404, code='NOT_FOUND')
        revoke_session(s, 'REVOKED_BY_USER')
        db.session.commit()
        audit('SESSION_REVOKED', user.user_id, 'SESSION', s.public_id)
        return ok({'message': 'Device signed out.'})
