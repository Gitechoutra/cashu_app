"""
Admin-only API. Every route is guarded by role_required(ADMIN) on the server.

Users & roles · platform stats · all payments · payment-gateway configuration
(secrets encrypted, never returned) · issuing banks · audit log.
"""

from datetime import timedelta
from decimal import Decimal

from flask import request
from flask_restx import Resource
from sqlalchemy import func, or_

from portal import db
from portal.extensions import limiter
from portal.helpers import encryption
from portal.helpers.audit import audit
from portal.helpers.auth import current_user, revoke_session, role_required
from portal.helpers.card_math import money
from portal.helpers.pagination import paged
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.validators import Validator, clean_text, validate_choice
from portal.models.audit_logs import AuditLogs
from portal.models.kyc_verifications import KycVerifications
from portal.models.base import iso, utcnow
from portal.models.card_issuers import CardIssuers
from portal.models.linked_cards import LinkedCards
from portal.models.payment_gateways import PaymentGateways, GatewayProvider
from portal.models.payment_transactions import PaymentTransactions, PaymentStatus
from portal.models.roles import Roles, RoleName
from portal.models.support_tickets import SupportTickets, TicketStatus
from portal.models.user_sessions import UserSessions, SessionStatus
from portal.models.users import Users, UserStatus
from portal.helpers.validators import normalize_mobile, validate_email, validate_staff_pin
from werkzeug.security import generate_password_hash
from portal.routes.bills.routes import serialize_payment

from . import ns, logger

admin_only = role_required(RoleName.ADMIN)


def _json():
    return request.get_json(silent=True) or {}


def _escape_like(v):
    return v.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def serialize_user(u):
    return {
        'user_id': u.public_id, 'full_name': u.full_name, 'mobile_number': u.masked_mobile,
        'role': u.role_name, 'role_display': u.role.display_name if u.role else None,
        'status': u.status, 'has_pin': bool(u.pin_hash), 'seed_managed': bool(u.seed_key),
        'email': u.email, 'pin_reset_required': bool(u.pin_reset_required),
        'cards': u.cards.filter_by(is_active=True).count(),
        'kyc_status': (KycVerifications.query.filter_by(user_id=u.user_id).first() or KycVerifications(status='NOT_STARTED')).status,
        'last_login': iso(u.last_login), 'created_on': iso(u.created_on),
    }


# ── Dashboard ───────────────────────────────────────────────────────────────

@ns.route('/stats')
class Stats(Resource):
    @ns.doc(description='Platform KPIs for the admin dashboard.')
    @admin_only
    def get(self):
        now = utcnow()
        since = now - timedelta(days=30)
        role_counts = dict(db.session.query(Roles.role_name, func.count(Users.user_id))
                           .join(Users, Users.role_id == Roles.role_id).group_by(Roles.role_name).all())
        pay = PaymentTransactions.query.filter(PaymentTransactions.created_at >= since)
        succeeded = pay.filter_by(status=PaymentStatus.SUCCESS)
        volume = db.session.query(func.coalesce(func.sum(PaymentTransactions.amount), 0)).filter(
            PaymentTransactions.created_at >= since, PaymentTransactions.status == PaymentStatus.SUCCESS).scalar()
        attempted = pay.filter(PaymentTransactions.status.in_([PaymentStatus.SUCCESS, PaymentStatus.FAILED])).count()
        daily = (db.session.query(func.date(PaymentTransactions.created_at), func.count(), func.coalesce(func.sum(PaymentTransactions.amount), 0))
                 .filter(PaymentTransactions.created_at >= now - timedelta(days=14),
                         PaymentTransactions.status == PaymentStatus.SUCCESS)
                 .group_by(func.date(PaymentTransactions.created_at)).all())
        return ok({
            'users': {'total': sum(role_counts.values()), 'by_role': role_counts,
                      'new_30d': Users.query.filter(Users.created_on >= since).count(),
                      'suspended': Users.query.filter_by(status=UserStatus.SUSPENDED).count()},
            'cards': {'active': LinkedCards.query.filter_by(is_active=True).count(),
                      'verified': LinkedCards.query.filter_by(is_active=True, verification_status='VERIFIED').count()},
            'payments_30d': {'count': pay.count(), 'successful': succeeded.count(), 'volume': money(volume),
                             'success_rate': round(succeeded.count() * 100 / attempted, 1) if attempted else None},
            'tickets': {'open': SupportTickets.query.filter(SupportTickets.status.in_(TicketStatus.ACTIVE)).count(),
                        'unassigned': SupportTickets.query.filter(SupportTickets.status.in_(TicketStatus.ACTIVE),
                                                                  SupportTickets.assigned_to.is_(None)).count()},
            'daily_payments': [{'date': str(d), 'count': c, 'volume': money(v)} for d, c, v in sorted(daily)],
        })


# ── Users & roles ───────────────────────────────────────────────────────────

@ns.route('/roles')
class RolesList(Resource):
    @admin_only
    def get(self):
        return ok({'roles': [{'role': r.role_name, 'display_name': r.display_name, 'description': r.description,
                              'users': r.users.count()} for r in Roles.query.order_by(Roles.role_id).all()]})


@ns.route('/users')
class UsersList(Resource):
    @ns.doc(description='Search users.', params={'q': 'name or last digits of mobile', 'role': 'ADMIN|SUPPORT|USER',
                                                 'status': 'ACTIVE|SUSPENDED', 'page': '', 'per_page': ''})
    @admin_only
    def get(self):
        q = Users.query.join(Roles)
        term = clean_text(request.args.get('q'))[:50]
        if term:
            like = f'%{_escape_like(term)}%'
            q = q.filter(or_(Users.full_name.ilike(like), Users.mobile_number.like(like)))
        if request.args.get('role') in RoleName.CHOICES:
            q = q.filter(Roles.role_name == request.args['role'])
        if request.args.get('status') in UserStatus.CHOICES:
            q = q.filter(Users.status == request.args['status'])
        return ok(paged(q.order_by(Users.created_on.desc()), serialize_user))

    @ns.doc(description='Invite a staff member: assigns a role to a mobile number. They sign in with OTP.')
    @limiter.limit('30 per hour')
    @admin_only
    def post(self):
        try:
            body = _json()
            v = Validator()
            mobile, e = normalize_mobile(body.get('mobile_number'))
            v.check('mobile_number', e)
            role, e = validate_choice(body.get('role'), RoleName.STAFF, 'Role', required=True)
            v.check('role', e)
            email, e = validate_email(body.get('email'), required=True)
            v.check('email', e)
            temp_pin, e = validate_staff_pin(body.get('temporary_pin'))
            v.check('temporary_pin', e)
            if not v.ok:
                return v.response()
            if Users.query.filter_by(email=email).first():
                return fail('This email is already in use.', 409, code='EMAIL_EXISTS')
            if Users.query.filter_by(mobile_number=mobile).first():
                return fail('This mobile number already has an account. Staff accounts must use a separate number.', 409,
                            code='USER_EXISTS')
            u = Users(mobile_number=mobile, email=email, role_id=Roles.id_for(role), status=UserStatus.ACTIVE,
                      full_name=clean_text(body.get('full_name'))[:100] or None,
                      pin_hash=generate_password_hash(temp_pin), pin_set_at=utcnow(), pin_reset_required=True)
            db.session.add(u)
            db.session.commit()
            audit('ADMIN_USER_CREATED', current_user().user_id, 'USER', u.public_id, details={'role': role})
            return ok({'user': serialize_user(u)}, 201)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'admin/users/post')


@ns.route('/users/<string:user_id>')
class UserAdmin(Resource):
    @ns.doc(description='Change role and/or status. Suspending or changing role signs the user out everywhere.')
    @admin_only
    def patch(self, user_id):
        try:
            me = current_user()
            u = Users.query.filter_by(public_id=user_id[:32]).first()
            if not u:
                return fail('User not found.', 404, code='NOT_FOUND')
            body = _json()
            if u.seed_key and ({'role', 'status'} & set(body)):
                file = 'seed_admin.py' if u.role_name == RoleName.ADMIN else 'seed_customersupport.py'
                return fail(f'This account is managed in seeders/{file}. Change or remove it there.', 409,
                            code='MANAGED_BY_SEED')
            v = Validator()
            role, e = validate_choice(body.get('role'), RoleName.CHOICES, 'Role')
            v.check('role', e)
            status, e = validate_choice(body.get('status'), UserStatus.CHOICES, 'Status')
            v.check('status', e)
            if not v.ok:
                return v.response()
            # Staff and customer accounts stay separate: roles move only between Admin and Customer Support.
            if role and (role == RoleName.USER) != (u.role_name == RoleName.USER):
                return fail('Customer and staff accounts are separate. Use Add staff to create a staff account.', 400,
                            code='ROLE_CHANGE_NOT_ALLOWED')
            if u.user_id == me.user_id and (role and role != RoleName.ADMIN or status == UserStatus.SUSPENDED):
                return fail("You can't remove your own admin access or suspend yourself.", 400, code='SELF_LOCKOUT')
            if role and role != RoleName.ADMIN and u.role_name == RoleName.ADMIN:
                admins = Users.query.join(Roles).filter(Roles.role_name == RoleName.ADMIN,
                                                        Users.status == UserStatus.ACTIVE).count()
                if admins <= 1:
                    return fail('At least one active Admin is required.', 400, code='LAST_ADMIN')

            before = {'role': u.role_name, 'status': u.status}
            if role:
                u.role_id = Roles.id_for(role)
            if status:
                u.status = status
            db.session.flush()
            db.session.refresh(u)
            if {'role': u.role_name, 'status': u.status} != before:
                # New permissions must take effect immediately: end every session.
                for s in UserSessions.query.filter_by(user_id=u.user_id, status=SessionStatus.ACTIVE):
                    revoke_session(s, 'ADMIN_CHANGE')
            db.session.commit()
            audit('ADMIN_USER_UPDATED', me.user_id, 'USER', u.public_id,
                  details={'before': before, 'after': {'role': u.role_name, 'status': u.status}})
            return ok({'user': serialize_user(u)})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'admin/users/patch')


@ns.route('/users/<string:user_id>/reset-pin')
class StaffPinReset(Resource):
    @ns.doc(description='Give a staff member a temporary 6-digit PIN (forgotten PIN). They must choose a new '
                        'PIN at next sign-in; all their sessions end now.')
    @limiter.limit('20 per hour')
    @admin_only
    def post(self, user_id):
        try:
            u = Users.query.filter_by(public_id=user_id[:32]).first()
            if not u or u.role_name not in RoleName.STAFF:
                return fail('Staff account not found.', 404, code='NOT_FOUND')
            if u.seed_key:
                return fail('This account is managed in the seed file — change its PIN there (or in .env).', 409,
                            code='MANAGED_BY_SEED')
            if u.user_id == current_user().user_id:
                return fail('Change your own PIN from Settings.', 400, code='SELF_RESET')
            pin, e = validate_staff_pin((request.get_json(silent=True) or {}).get('temporary_pin'))
            if e:
                return fail(e, 400, code='VALIDATION_ERROR', errors={'temporary_pin': e})
            u.pin_hash, u.pin_set_at, u.pin_reset_required = generate_password_hash(pin), utcnow(), True
            u.pin_failed_attempts, u.pin_locked_until = 0, None
            for s in UserSessions.query.filter_by(user_id=u.user_id, status=SessionStatus.ACTIVE):
                revoke_session(s, 'ADMIN_PIN_RESET')
            db.session.commit()
            audit('STAFF_PIN_RESET', current_user().user_id, 'USER', u.public_id)
            return ok({'message': 'Temporary PIN set. Share it securely; they must change it at next sign-in.'})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'admin/users/reset-pin')


# ── Payments ────────────────────────────────────────────────────────────────

@ns.route('/payments')
class Payments(Resource):
    @ns.doc(description='All card-bill payments.', params={'status': 'CREATED|PENDING|SUCCESS|FAILED',
                                                           'q': 'receipt / order / payment reference'})
    @admin_only
    def get(self):
        q = PaymentTransactions.query
        if request.args.get('status') in (PaymentStatus.CREATED, PaymentStatus.PENDING, PaymentStatus.SUCCESS, PaymentStatus.FAILED):
            q = q.filter_by(status=request.args['status'])
        term = clean_text(request.args.get('q'))[:64]
        if term:
            q = q.filter(or_(PaymentTransactions.receipt_number == term, PaymentTransactions.provider_order_id == term,
                             PaymentTransactions.provider_payment_id == term))

        def ser(p):
            d = serialize_payment(p)
            u = db.session.get(Users, p.user_id)
            d['customer'] = {'user_id': u.public_id, 'full_name': u.full_name, 'mobile_number': u.masked_mobile}
            return d
        return ok(paged(q.order_by(PaymentTransactions.created_at.desc()), ser))


# ── Payment gateways ────────────────────────────────────────────────────────

def _mask(s):
    return f'••••••{s[-4:]}' if s and len(s) > 4 else ('set' if s else None)


def serialize_gateway(g):
    secret = encryption.decrypt(g.encrypted_key_secret) if g.encrypted_key_secret else ''
    hook = encryption.decrypt(g.encrypted_webhook_secret) if g.encrypted_webhook_secret else ''
    return {'gateway_id': g.gateway_id, 'provider': g.provider, 'display_name': g.display_name, 'mode': g.mode,
            'key_id': g.key_id, 'key_secret': _mask(secret), 'webhook_secret': _mask(hook),
            'is_active': g.is_active, 'updated_at': iso(g.updated_at)}


def _validate_gateway(body, partial=False):
    v = Validator()
    out = {}
    if not partial or 'display_name' in body:
        out['display_name'] = clean_text(body.get('display_name'))[:60]
        if not out['display_name']:
            v.check('display_name', 'Name is required.')
    if not partial or 'key_id' in body:
        kid = str(body.get('key_id') or '').strip()
        if not (kid.startswith('rzp_test_') or kid.startswith('rzp_live_')) or len(kid) > 64:
            v.check('key_id', 'Razorpay key id must start with rzp_test_ or rzp_live_.')
        out['key_id'] = kid
    for f in ('key_secret', 'webhook_secret'):
        if f in body and body[f] not in (None, ''):
            val = str(body[f]).strip()
            if len(val) < 8 or len(val) > 128:
                v.check(f, 'Secret looks invalid.')
            out[f] = val
    if not partial and not out.get('key_secret'):
        v.check('key_secret', 'Key secret is required.')
    return out, v


@ns.route('/gateways')
class Gateways(Resource):
    @ns.doc(description='Configured payment gateways (secrets masked). Shows which source is active.')
    @admin_only
    def get(self):
        from portal.helpers.razorpay_helper import credentials, payment_config
        rows = PaymentGateways.query.order_by(PaymentGateways.created_at.desc()).all()
        cfg = payment_config()
        cfg.pop('key_id', None)
        return ok({'gateways': [serialize_gateway(g) for g in rows], 'active_source': credentials()['source'],
                   'status': cfg, 'providers': GatewayProvider.CHOICES})

    @ns.doc(description='Add a Razorpay gateway configuration.')
    @limiter.limit('20 per hour')
    @admin_only
    def post(self):
        try:
            body = _json()
            data, v = _validate_gateway(body)
            if not v.ok:
                return v.response()
            g = PaymentGateways(provider=GatewayProvider.RAZORPAY, display_name=data['display_name'],
                                key_id=data['key_id'], mode='live' if data['key_id'].startswith('rzp_live_') else 'test',
                                encrypted_key_secret=encryption.encrypt(data['key_secret']),
                                encrypted_webhook_secret=encryption.encrypt(data['webhook_secret']) if data.get('webhook_secret') else None,
                                is_active=False, updated_by=current_user().user_id)
            db.session.add(g)
            db.session.commit()
            audit('GATEWAY_CREATED', current_user().user_id, 'GATEWAY', g.gateway_id, details={'mode': g.mode})
            return ok({'gateway': serialize_gateway(g)}, 201)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'admin/gateways/post')


@ns.route('/gateways/<int:gateway_id>')
class Gateway(Resource):
    @ns.doc(description='Update a gateway. Leave secrets empty to keep the stored values. '
                        'Set is_active=true to make it the only active gateway.')
    @admin_only
    def patch(self, gateway_id):
        try:
            g = db.session.get(PaymentGateways, gateway_id)
            if not g:
                return fail('Gateway not found.', 404, code='NOT_FOUND')
            body = _json()
            data, v = _validate_gateway(body, partial=True)
            if not v.ok:
                return v.response()
            if 'display_name' in data:
                g.display_name = data['display_name']
            if 'key_id' in data:
                g.key_id = data['key_id']
                g.mode = 'live' if g.key_id.startswith('rzp_live_') else 'test'
            if data.get('key_secret'):
                g.encrypted_key_secret = encryption.encrypt(data['key_secret'])
            if data.get('webhook_secret'):
                g.encrypted_webhook_secret = encryption.encrypt(data['webhook_secret'])
            if 'is_active' in body:
                if body['is_active'] is True:
                    PaymentGateways.query.filter(PaymentGateways.gateway_id != g.gateway_id) \
                        .update({'is_active': False}, synchronize_session=False)
                g.is_active = body['is_active'] is True
            g.updated_by = current_user().user_id
            db.session.commit()
            audit('GATEWAY_UPDATED', current_user().user_id, 'GATEWAY', g.gateway_id,
                  details={'fields': sorted(k for k in body if 'secret' not in k), 'secrets_changed':
                           sorted(k for k in ('key_secret', 'webhook_secret') if data.get(k)), 'active': g.is_active})
            return ok({'gateway': serialize_gateway(g)})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'admin/gateways/patch')

    @admin_only
    def delete(self, gateway_id):
        g = db.session.get(PaymentGateways, gateway_id)
        if not g:
            return fail('Gateway not found.', 404, code='NOT_FOUND')
        if g.is_active:
            return fail('Deactivate this gateway before deleting it.', 400, code='GATEWAY_ACTIVE')
        db.session.delete(g)
        db.session.commit()
        audit('GATEWAY_DELETED', current_user().user_id, 'GATEWAY', gateway_id)
        return ok({'message': 'Gateway deleted.'})


@ns.route('/gateways/<int:gateway_id>/test')
class GatewayTest(Resource):
    @ns.doc(description='Check the stored credentials against Razorpay (read-only API call; no money moves).')
    @limiter.limit('10 per minute')
    @admin_only
    def post(self, gateway_id):
        import requests
        from flask import current_app
        g = db.session.get(PaymentGateways, gateway_id)
        if not g:
            return fail('Gateway not found.', 404, code='NOT_FOUND')
        try:
            r = requests.get(current_app.config['RAZORPAY_API_BASE'] + '/orders', params={'count': 1},
                             auth=(g.key_id, encryption.decrypt(g.encrypted_key_secret)), timeout=15)
        except requests.RequestException:
            return fail('Could not reach Razorpay.', 502, code='GATEWAY_UNREACHABLE')
        if r.status_code == 200:
            return ok({'ok': True, 'message': f'Credentials valid ({g.mode} mode).'})
        return fail('Razorpay rejected these credentials.' if r.status_code in (400, 401) else
                    f'Razorpay returned HTTP {r.status_code}.', 400, code='GATEWAY_AUTH_FAILED')


# ── Issuing banks ───────────────────────────────────────────────────────────

@ns.route('/issuers')
class Issuers(Resource):
    @admin_only
    def get(self):
        rows = CardIssuers.query.order_by(CardIssuers.sort_order, CardIssuers.name).all()
        counts = dict(db.session.query(LinkedCards.issuer_id, func.count()).filter_by(is_active=True)
                      .group_by(LinkedCards.issuer_id).all())
        return ok({'issuers': [{**i.to_dict(), 'is_active': i.is_active, 'sort_order': i.sort_order,
                                'cards': counts.get(i.issuer_id, 0)} for i in rows]})


@ns.route('/issuers/<int:issuer_id>')
class Issuer(Resource):
    @ns.doc(description='Enable/disable a bank or change whether it is in the Popular grid.')
    @admin_only
    def patch(self, issuer_id):
        i = db.session.get(CardIssuers, issuer_id)
        if not i:
            return fail('Bank not found.', 404, code='NOT_FOUND')
        body = _json()
        if 'is_active' in body:
            i.is_active = body['is_active'] is True
        if 'popular' in body and i.code != 'OTHER':
            i.sort_order = 5 if body['popular'] is True else 100
        db.session.commit()
        audit('ISSUER_UPDATED', current_user().user_id, 'ISSUER', i.code,
              details={'is_active': i.is_active, 'sort_order': i.sort_order})
        return ok({'issuer': {**i.to_dict(), 'is_active': i.is_active}})


# ── Audit log ───────────────────────────────────────────────────────────────

@ns.route('/audit-logs')
class Audit(Resource):
    @ns.doc(params={'action': 'filter by action', 'page': '', 'per_page': ''})
    @admin_only
    def get(self):
        q = AuditLogs.query
        if request.args.get('action'):
            q = q.filter(AuditLogs.action == clean_text(request.args['action'])[:60].upper())
        users = {}

        def ser(a):
            if a.user_id and a.user_id not in users:
                u = db.session.get(Users, a.user_id)
                users[a.user_id] = {'full_name': u.full_name, 'mobile_number': u.masked_mobile, 'role': u.role_name} if u else None
            return {'log_id': a.log_id, 'action': a.action, 'status': a.status, 'entity_type': a.entity_type,
                    'entity_id': a.entity_id, 'details': a.details, 'ip_address': a.ip_address,
                    'created_on': iso(a.created_on), 'actor': users.get(a.user_id)}
        return ok(paged(q.order_by(AuditLogs.created_on.desc()), ser, default=30))
