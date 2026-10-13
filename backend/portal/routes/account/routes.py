"""
Account: profile, security preferences, login activity, devices (all roles),
plus KYC status and bank accounts (customers only).
"""

import hashlib
import hmac
import re

from flask import current_app, g, request
from flask_restx import Resource
from sqlalchemy.exc import IntegrityError

from portal import db
from portal.extensions import limiter
from portal.helpers import encryption
from portal.helpers.activity import security_prefs
from portal.helpers.audit import audit
from portal.helpers.auth import auth_required, current_user, customer_required, revoke_session
from portal.helpers.pagination import paged
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.validators import Validator, clean_text, validate_bank_name, validate_name
from portal.models.bank_accounts import BankAccounts, BankAccountVerification
from portal.models.base import iso, utcnow
from portal.models.device_bindings import DeviceBindings
from portal.models.kyc_verifications import KycVerifications, KycStatus
from portal.models.login_history import LoginHistory
from portal.models.user_profiles import UserProfiles
from portal.models.user_sessions import UserSessions, SessionStatus

from . import ns, logger

EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$')
IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
ACCOUNT_RE = re.compile(r'^\d{9,18}$')
LANGUAGES = {'en': 'English', 'hi': 'Hindi', 'te': 'Telugu', 'ta': 'Tamil', 'kn': 'Kannada', 'ml': 'Malayalam',
             'mr': 'Marathi', 'bn': 'Bengali', 'gu': 'Gujarati'}
IDLE_CHOICES = [1, 2, 5, 10, 15]
MAX_BANK_ACCOUNTS = 5


def _json():
    return request.get_json(silent=True) or {}


# ── Profile ─────────────────────────────────────────────────────────────────

def _profile(user):
    return UserProfiles.query.filter_by(user_id=user.user_id).first() or UserProfiles(user_id=user.user_id)


def serialize_profile(user, p):
    return {'full_name': user.full_name, 'mobile_number': user.masked_mobile, 'email': p.email,
            'email_verified': bool(p.email_verified), 'city': p.city, 'state': p.state,
            'preferred_language': p.preferred_language or 'en', 'languages': LANGUAGES}


@ns.route('/profile')
class Profile(Resource):
    @auth_required
    def get(self):
        u = current_user()
        return ok(serialize_profile(u, _profile(u)))

    @ns.doc(description='Update email, city, state and language. (Name: PATCH /authentication/me.)')
    @auth_required
    def patch(self):
        try:
            u = current_user()
            body = _json()
            v = Validator()
            p = _profile(u)
            if 'email' in body:
                email = clean_text(body.get('email')).lower()[:254]
                if email and not EMAIL_RE.match(email):
                    v.check('email', 'Enter a valid email address.')
                elif email != (p.email or ''):
                    p.email, p.email_verified = email or None, False
            for f in ('city', 'state'):
                if f in body:
                    val = clean_text(body.get(f))[:60]
                    if val and not re.match(r"^[A-Za-z][A-Za-z .'-]*$", val):
                        v.check(f, 'Use letters only.')
                    setattr(p, f, val or None)
            if 'preferred_language' in body:
                lang = str(body.get('preferred_language') or 'en')
                if lang not in LANGUAGES:
                    v.check('preferred_language', 'Unsupported language.')
                p.preferred_language = lang
            if not v.ok:
                db.session.rollback()
                return v.response()
            db.session.add(p)
            db.session.commit()
            return ok(serialize_profile(u, p))
        except Exception:
            db.session.rollback()
            return server_error(logger, 'account/profile')


# ── Security preferences ────────────────────────────────────────────────────

@ns.route('/preferences')
class Preferences(Resource):
    @auth_required
    def get(self):
        p = security_prefs(current_user().user_id)
        server = current_app.config['SESSION_IDLE_LOCK_MINUTES']
        return ok({'idle_lock_minutes': p.idle_lock_minutes, 'server_idle_lock_minutes': server,
                   'idle_choices': [m for m in IDLE_CHOICES if m <= server],
                   'login_alerts': p.login_alerts, 'payment_alerts': p.payment_alerts})

    @ns.doc(description='idle_lock_minutes (null = default, can only be shorter than the server limit), '
                        'login_alerts, payment_alerts.')
    @auth_required
    def patch(self):
        try:
            u = current_user()
            body = _json()
            p = security_prefs(u.user_id)
            server = current_app.config['SESSION_IDLE_LOCK_MINUTES']
            if 'idle_lock_minutes' in body:
                m = body['idle_lock_minutes']
                if m is not None and (not isinstance(m, int) or isinstance(m, bool) or m not in IDLE_CHOICES or m > server):
                    return fail(f'Choose one of {[x for x in IDLE_CHOICES if x <= server]} minutes.', 400, code='VALIDATION_ERROR')
                p.idle_lock_minutes = m
            for f in ('login_alerts', 'payment_alerts'):
                if f in body:
                    if not isinstance(body[f], bool):
                        return fail(f'{f} must be true or false.', 400, code='VALIDATION_ERROR')
                    setattr(p, f, body[f])
            db.session.add(p)
            db.session.commit()
            audit('SECURITY_PREFERENCES_UPDATED', u.user_id, details={k: body[k] for k in body if k in
                                                                       ('idle_lock_minutes', 'login_alerts', 'payment_alerts')})
            return self.get()
        except Exception:
            db.session.rollback()
            return server_error(logger, 'account/preferences')


# ── Login activity & devices ────────────────────────────────────────────────

@ns.route('/login-history')
class History(Resource):
    @auth_required
    def get(self):
        q = LoginHistory.query.filter_by(user_id=current_user().user_id).order_by(LoginHistory.created_at.desc())
        devices = {d.device_binding_id: d.device_name for d in
                   DeviceBindings.query.filter_by(user_id=current_user().user_id)}
        return ok(paged(q, lambda h: {'event': h.event, 'status': h.status, 'reason': h.failure_reason,
                                      'device': devices.get(h.device_binding_id), 'ip_address': h.ip_address,
                                      'created_at': iso(h.created_at)}, default=15, maximum=50))


@ns.route('/devices')
class Devices(Resource):
    @auth_required
    def get(self):
        u = current_user()
        cur = g.session.device_binding_id
        rows = (DeviceBindings.query.filter_by(user_id=u.user_id, revoked_at=None)
                .order_by(DeviceBindings.last_seen_at.desc()).all())
        return ok({'devices': [{'device_id': d.public_id, 'name': d.device_name, 'current': d.device_binding_id == cur,
                                'first_seen_at': iso(d.first_seen_at), 'last_seen_at': iso(d.last_seen_at),
                                'active_sessions': UserSessions.query.filter_by(device_binding_id=d.device_binding_id,
                                                                                status=SessionStatus.ACTIVE).count()}
                               for d in rows]})


@ns.route('/devices/<string:device_id>')
class Device(Resource):
    @ns.doc(description='Remove a device: signs out all of its sessions.')
    @auth_required
    def delete(self, device_id):
        u = current_user()
        d = DeviceBindings.query.filter_by(public_id=device_id[:32], user_id=u.user_id, revoked_at=None).first()
        if not d:
            return fail('Device not found.', 404, code='NOT_FOUND')
        if d.device_binding_id == g.session.device_binding_id:
            return fail('Use Sign out to remove this device.', 400, code='CURRENT_DEVICE')
        d.revoked_at = utcnow()
        for s in UserSessions.query.filter_by(device_binding_id=d.device_binding_id, status=SessionStatus.ACTIVE):
            revoke_session(s, 'DEVICE_REMOVED')
        db.session.commit()
        audit('DEVICE_REMOVED', u.user_id, 'DEVICE', d.public_id)
        return ok({'message': 'Device signed out.'})


# ── KYC (status only) ───────────────────────────────────────────────────────

def kyc_payload(user_id):
    k = KycVerifications.query.filter_by(user_id=user_id).first()
    return {'status': k.status if k else KycStatus.NOT_STARTED, 'method': k.method if k else None,
            'verified_at': iso(k.verified_at) if k else None, 'rejection_reason': k.rejection_reason if k else None,
            'provider_configured': False,
            'message': 'e-KYC provider not configured. KYC is not required in test mode.'}


@ns.route('/kyc')
class Kyc(Resource):
    @ns.doc(description='KYC status. Starting KYC needs a licensed e-KYC provider (DigiLocker / CKYC / Video KYC).')
    @customer_required
    def get(self):
        return ok(kyc_payload(current_user().user_id))


# ── Bank accounts ───────────────────────────────────────────────────────────

def _fingerprint(account_number):
    key = (current_app.config.get('SECRET_KEY') or '').encode()
    return hmac.new(key, account_number.encode(), hashlib.sha256).hexdigest()


def serialize_bank(b):
    return {'bank_account_id': b.public_id, 'account_holder_name': b.account_holder_name, 'bank_name': b.bank_name,
            'ifsc': b.ifsc, 'masked_account': f'XXXX XXXX {b.account_last4}', 'account_type': b.account_type,
            'verification_status': b.verification_status, 'is_primary': b.is_primary, 'created_at': iso(b.created_at)}


@ns.route('/bank-accounts')
class BankAccountList(Resource):
    @customer_required
    def get(self):
        rows = (BankAccounts.query.filter_by(user_id=current_user().user_id)
                .order_by(BankAccounts.is_primary.desc(), BankAccounts.created_at).all())
        return ok({'bank_accounts': [serialize_bank(b) for b in rows],
                   'verification_configured': False,
                   'message': 'Account verification (penny drop) is not configured — accounts are saved as not verified.'})

    @ns.doc(description='Save a bank account. The account number is encrypted; only the last 4 digits are returned.')
    @limiter.limit('10 per hour')
    @customer_required
    def post(self):
        try:
            u = current_user()
            body = _json()
            v = Validator()
            holder, e = validate_name(body.get('account_holder_name'), required=True)
            v.check('account_holder_name', e)
            bank, e = validate_bank_name(body.get('bank_name'))
            v.check('bank_name', e)
            ifsc = str(body.get('ifsc') or '').strip().upper()
            if not IFSC_RE.match(ifsc):
                v.check('ifsc', 'Enter a valid 11-character IFSC (e.g. HDFC0001234).')
            acct = re.sub(r'\s', '', str(body.get('account_number') or ''))
            if not ACCOUNT_RE.match(acct):
                v.check('account_number', 'Account number must be 9 to 18 digits.')
            elif str(body.get('confirm_account_number') or '').replace(' ', '') != acct:
                v.check('confirm_account_number', 'Account numbers do not match.')
            atype = str(body.get('account_type') or 'SAVINGS').upper()
            if atype not in ('SAVINGS', 'CURRENT'):
                v.check('account_type', 'Choose savings or current.')
            if not v.ok:
                return v.response()
            if BankAccounts.query.filter_by(user_id=u.user_id).count() >= MAX_BANK_ACCOUNTS:
                return fail(f'You can save up to {MAX_BANK_ACCOUNTS} bank accounts.', 400, code='LIMIT')
            fp = _fingerprint(acct)
            if BankAccounts.query.filter_by(user_id=u.user_id, account_fingerprint=fp).first():
                return fail('This bank account is already saved.', 409, code='DUPLICATE')
            first = BankAccounts.query.filter_by(user_id=u.user_id).count() == 0
            b = BankAccounts(user_id=u.user_id, account_holder_name=holder, bank_name=bank, ifsc=ifsc,
                             account_number_encrypted=encryption.encrypt(acct), account_last4=acct[-4:],
                             account_fingerprint=fp, account_type=atype, is_primary=first,
                             verification_status=BankAccountVerification.UNVERIFIED)
            db.session.add(b)
            db.session.commit()
            audit('BANK_ACCOUNT_ADDED', u.user_id, 'BANK_ACCOUNT', b.public_id, details={'ifsc': ifsc, 'last4': acct[-4:]})
            return ok({'bank_account': serialize_bank(b)}, 201)
        except IntegrityError:
            db.session.rollback()
            return fail('This bank account is already saved.', 409, code='DUPLICATE')
        except Exception:
            db.session.rollback()
            return server_error(logger, 'account/bank-accounts/post')


@ns.route('/bank-accounts/<string:account_id>')
class BankAccount(Resource):
    @customer_required
    def delete(self, account_id):
        u = current_user()
        b = BankAccounts.query.filter_by(public_id=account_id[:32], user_id=u.user_id).first()
        if not b:
            return fail('Bank account not found.', 404, code='NOT_FOUND')
        was_primary = b.is_primary
        db.session.delete(b)
        db.session.flush()
        if was_primary:
            nxt = BankAccounts.query.filter_by(user_id=u.user_id).order_by(BankAccounts.created_at).first()
            if nxt:
                nxt.is_primary = True
        db.session.commit()
        audit('BANK_ACCOUNT_REMOVED', u.user_id, 'BANK_ACCOUNT', account_id[:32])
        return ok({'message': 'Bank account removed.'})


@ns.route('/bank-accounts/<string:account_id>/primary')
class BankAccountPrimary(Resource):
    @customer_required
    def post(self, account_id):
        u = current_user()
        b = BankAccounts.query.filter_by(public_id=account_id[:32], user_id=u.user_id).first()
        if not b:
            return fail('Bank account not found.', 404, code='NOT_FOUND')
        BankAccounts.query.filter_by(user_id=u.user_id).update({'is_primary': False})
        b.is_primary = True
        db.session.commit()
        return ok({'bank_account': serialize_bank(b)})
