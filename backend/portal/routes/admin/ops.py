"""Admin operations: platform settings, payment reconciliation and payment exceptions."""

from datetime import timedelta

from flask import request
from flask_restx import Resource

from portal import db
from portal.extensions import limiter
from portal.helpers.audit import audit
from portal.helpers.auth import current_user, role_required
from portal.helpers.pagination import paged
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.settings import cast, validate_value
from portal.models.admin_settings import AdminSettings
from portal.models.base import iso, utcnow
from portal.models.payment_transactions import PaymentTransactions, PaymentStatus
from portal.models.reconciliation import Reconciliation
from portal.models.roles import RoleName
from portal.models.transaction_errors import TransactionErrors

from . import ns, logger

admin_only = role_required(RoleName.ADMIN)


def serialize_setting(s):
    return {'key': s.key, 'label': s.label, 'description': s.description, 'value_type': s.value_type,
            'value': cast(s.value, s.value_type), 'raw_value': s.value or '', 'is_public': s.is_public,
            'updated_at': iso(s.updated_at)}


@ns.route('/platform-settings')
class PlatformSettings(Resource):
    @admin_only
    def get(self):
        return ok({'settings': [serialize_setting(s) for s in AdminSettings.query.order_by(AdminSettings.setting_id)]})

    @ns.doc(description='Update one or more settings: {"values": {"KEY": "value", ...}}')
    @admin_only
    def patch(self):
        try:
            values = (request.get_json(silent=True) or {}).get('values') or {}
            if not isinstance(values, dict) or not values:
                return fail('Nothing to update.', 400, code='VALIDATION_ERROR')
            errors, changed = {}, {}
            rows = {s.key: s for s in AdminSettings.query.filter(AdminSettings.key.in_(list(values)))}
            for key, raw in values.items():
                row = rows.get(key)
                if not row:
                    errors[key] = 'Unknown setting.'
                    continue
                norm, err = validate_value(raw, row.value_type)
                if err:
                    errors[key] = err
                    continue
                if norm != (row.value or ''):
                    changed[key] = {'from': row.value, 'to': norm}
                    row.value, row.updated_by = norm, current_user().user_id
            if not errors and {'MIN_CARD_PAYMENT_INR', 'MAX_CARD_PAYMENT_INR'} & set(values):
                # Rows were updated in-session above, so these reflect the new values.
                current = {s.key: cast(s.value, s.value_type) for s in AdminSettings.query.filter(
                    AdminSettings.key.in_(['MIN_CARD_PAYMENT_INR', 'MAX_CARD_PAYMENT_INR']))}
                lo, hi = current.get('MIN_CARD_PAYMENT_INR'), current.get('MAX_CARD_PAYMENT_INR')
                if lo is not None and hi is not None and lo > hi:
                    errors['MIN_CARD_PAYMENT_INR'] = 'Minimum cannot be greater than maximum.'
            if errors:
                db.session.rollback()
                return fail(next(iter(errors.values())), 400, code='VALIDATION_ERROR', errors=errors)
            db.session.commit()
            if changed:
                audit('PLATFORM_SETTINGS_UPDATED', current_user().user_id, 'SETTINGS', None, details=changed)
            return self.get()
        except Exception:
            db.session.rollback()
            return server_error(logger, 'admin/platform-settings')


@ns.route('/reconciliation')
class ReconList(Resource):
    @ns.doc(params={'result': 'MATCHED|UPDATED|MISMATCH|ERROR'})
    @admin_only
    def get(self):
        q = Reconciliation.query
        if request.args.get('result') in ('MATCHED', 'UPDATED', 'MISMATCH', 'ERROR'):
            q = q.filter_by(result=request.args['result'])

        def ser(r):
            p = db.session.get(PaymentTransactions, r.payment_id)
            return {'recon_id': r.recon_id, 'receipt_number': p.receipt_number if p else None,
                    'provider_order_id': p.provider_order_id if p else None, 'source': r.source,
                    'status_before': r.status_before, 'status_after': r.status_after,
                    'gateway_status': r.gateway_status, 'result': r.result, 'note': r.note,
                    'created_at': iso(r.created_at)}
        res = paged(q.order_by(Reconciliation.created_at.desc()), ser, default=25)
        res['open_payments'] = PaymentTransactions.query.filter(
            PaymentTransactions.status.in_(PaymentStatus.OPEN),
            PaymentTransactions.created_at >= utcnow() - timedelta(days=2)).count()
        return ok(res)


@ns.route('/reconcile')
class ReconRun(Resource):
    @ns.doc(description='Check every open payment from the last 48 hours against Razorpay now.')
    @limiter.limit('6 per hour')
    @admin_only
    def post(self):
        from portal.routes.bills.routes import reconcile
        rows = (PaymentTransactions.query.filter(PaymentTransactions.status.in_(PaymentStatus.OPEN),
                                                 PaymentTransactions.created_at >= utcnow() - timedelta(days=2),
                                                 ~PaymentTransactions.provider_order_id.like('pending-%'))
                .limit(200).all())
        summary = {'checked': 0, 'updated': 0, 'errors': 0}
        for p in rows:
            before = p.status
            try:
                reconcile(p, source='ADMIN_RUN')
                db.session.commit()
                summary['checked'] += 1
                summary['updated'] += int(p.status != before)
            except Exception:
                db.session.rollback()
                summary['errors'] += 1
        audit('ADMIN_RECONCILE_RUN', current_user().user_id, details=summary)
        return ok(summary)


@ns.route('/transaction-errors')
class TxnErrors(Resource):
    @ns.doc(params={'resolved': 'true|false (default false)'})
    @admin_only
    def get(self):
        resolved = request.args.get('resolved', 'false') == 'true'
        q = TransactionErrors.query.filter_by(is_resolved=resolved)

        def ser(e):
            p = db.session.get(PaymentTransactions, e.payment_id) if e.payment_id else None
            return {'error_id': e.error_id, 'stage': e.stage, 'error_code': e.error_code, 'message': e.message,
                    'receipt_number': p.receipt_number if p else None, 'payment_status': p.status if p else None,
                    'is_resolved': e.is_resolved, 'resolved_at': iso(e.resolved_at), 'created_at': iso(e.created_at)}
        res = paged(q.order_by(TransactionErrors.created_at.desc()), ser, default=25)
        res['unresolved'] = TransactionErrors.query.filter_by(is_resolved=False).count()
        return ok(res)


@ns.route('/transaction-errors/<int:error_id>/resolve')
class TxnErrorResolve(Resource):
    @admin_only
    def post(self, error_id):
        e = db.session.get(TransactionErrors, error_id)
        if not e:
            return fail('Not found.', 404, code='NOT_FOUND')
        e.is_resolved, e.resolved_by, e.resolved_at = True, current_user().user_id, utcnow()
        db.session.commit()
        audit('TRANSACTION_ERROR_RESOLVED', current_user().user_id, 'TXN_ERROR', error_id)
        return ok({'message': 'Marked as resolved.'})
