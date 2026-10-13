"""
Credit card bills and payments (Razorpay).

A payment's status is changed ONLY by data fetched from Razorpay server-to-server
(after the checkout signature verifies) or by a signature-verified webhook. The
browser can never mark a payment successful.

Collection vs settlement: Razorpay collects the money into the merchant account.
Crediting the card issuer requires a BBPS bill-settlement partner; until one is
configured, settlement_status is NOT_CONFIGURED and live mode is refused.
"""

import secrets
from datetime import timedelta
from decimal import Decimal

from flask import current_app, request
from flask_restx import Resource
from sqlalchemy.exc import IntegrityError

from portal import db
from portal.extensions import limiter
from portal.helpers import card_service as svc
from portal.helpers import razorpay_helper as rzp
from portal.helpers.audit import audit
from portal.helpers.auth import customer_required, current_user
from portal.helpers.card_math import money
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.validators import Validator, validate_amount, validate_idempotency_key
from portal.models.base import iso, utcnow
from portal.models.linked_cards import LinkedCards
from portal.models.payment_transactions import PaymentTransactions, PaymentStatus, SettlementStatus
from portal.models.notifications import NotificationType
from portal.models.reconciliation import Reconciliation, ReconResult
from portal.models.transaction_errors import TransactionErrors
from portal.helpers.activity import notify
from portal.helpers.settings import get_setting

from . import ns, logger

MIN_PAYMENT = Decimal('1.00')
RECONCILE_INTERVAL = timedelta(seconds=10)


def _json():
    return request.get_json(silent=True) or {}


def serialize_payment(p):
    card = p.card
    return {
        'payment_id': p.public_id,
        'card_id': card.public_id if card else None,
        'card_nickname': card.card_nickname if card else None,
        'issuer_name': card.issuer_name if card else None,
        'masked_number': f'•••• {card.last_four_digits}' if card else None,
        'amount': money(p.amount),
        'currency': p.currency,
        'status': p.status,
        'settlement_status': p.settlement_status,
        'provider': p.provider,
        'provider_mode': p.provider_mode,
        'provider_order_id': p.provider_order_id,
        'provider_payment_id': p.provider_payment_id,
        'payment_method': p.payment_method,
        'receipt_number': p.receipt_number,
        'failure_reason': p.failure_reason,
        'verified_via': p.verified_via,
        'created_at': iso(p.created_at),
        'completed_at': iso(p.completed_at),
    }


def record_exception(payment_id, user_id, stage, code, message):
    """Persist a payment exception in its own transaction (the request's own work
    has usually just been rolled back). Never include secrets or signatures."""
    try:
        db.session.add(TransactionErrors(payment_id=payment_id, user_id=user_id, stage=stage,
                                         error_code=code[:40], message=message[:255]))
        if payment_id:
            p = db.session.get(PaymentTransactions, payment_id)
            db.session.add(Reconciliation(payment_id=payment_id, source=stage,
                                          status_before=p.status if p else None, status_after=p.status if p else None,
                                          result=ReconResult.MISMATCH if code == 'GATEWAY_DATA_MISMATCH' else ReconResult.ERROR,
                                          note=message[:255]))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('[bills] could not record transaction error')


def _notify_status(txn):
    card = txn.card
    label = f'{card.card_nickname} ending {card.last_four_digits}' if card else 'your card'
    if txn.status == PaymentStatus.SUCCESS:
        notify(txn.user_id, NotificationType.PAYMENT, f'Payment of {money(txn.amount)} INR successful',
               f'Bill payment for {label} was confirmed. Receipt {txn.receipt_number}.', link='/user/bills',
               dedupe_key=f'pay:{txn.payment_id}:SUCCESS')
    elif txn.status == PaymentStatus.FAILED:
        notify(txn.user_id, NotificationType.PAYMENT, f'Payment of {money(txn.amount)} INR failed',
               txn.failure_reason or 'The payment did not go through.', link='/user/bills',
               dedupe_key=f'pay:{txn.payment_id}:FAILED')


def apply_gateway_payment(txn, entity, via):
    """Update txn from a Razorpay payment entity obtained server-side. Validates
    that the entity really belongs to this order and amount. Records the check in
    `reconciliation` and notifies the customer when the status changes."""
    if entity.get('order_id') != txn.provider_order_id:
        raise ValueError('order mismatch')
    expected_paise = int((Decimal(txn.amount) * 100).to_integral_value())
    if int(entity.get('amount', -1)) != expected_paise or entity.get('currency') != txn.currency:
        raise ValueError('amount mismatch')

    before = txn.status
    _apply_status(txn, entity, via)
    db.session.add(Reconciliation(payment_id=txn.payment_id, source=via, status_before=before,
                                  status_after=txn.status, gateway_status=str(entity.get('status'))[:20],
                                  result=ReconResult.UPDATED if txn.status != before else ReconResult.MATCHED))
    if txn.status != before:
        _notify_status(txn)
    return txn


def _apply_status(txn, entity, via):
    gw_status = entity.get('status')
    if txn.status == PaymentStatus.SUCCESS:
        return txn                                          # terminal
    pid = entity.get('id')
    if gw_status == 'captured':
        other = PaymentTransactions.query.filter(PaymentTransactions.provider_payment_id == pid,
                                                 PaymentTransactions.payment_id != txn.payment_id).first()
        if other:
            raise ValueError('payment id already used')
        txn.status = PaymentStatus.SUCCESS
        txn.provider_payment_id = pid
        txn.payment_method = (entity.get('method') or '')[:30] or None
        txn.completed_at = utcnow()
        txn.failure_reason = None
        txn.settlement_status = (SettlementStatus.PENDING if current_app.config.get('BILL_SETTLEMENT_PROVIDER')
                                 else SettlementStatus.NOT_CONFIGURED)
    elif gw_status == 'authorized':
        txn.status = PaymentStatus.PENDING
        txn.provider_payment_id = txn.provider_payment_id or pid
    elif gw_status == 'failed' and txn.status in PaymentStatus.OPEN:
        txn.status = PaymentStatus.FAILED
        txn.failure_reason = (entity.get('error_description') or 'Payment failed at the provider.')[:255]
    txn.verified_via = via
    txn.last_reconciled_at = utcnow()
    return txn


def reconcile(txn, source='RECONCILE'):
    """Pull the truth for an open payment from Razorpay (all attempts on the order).
    Gateway errors / mismatches are recorded as transaction errors and re-raised."""
    pid, uid = txn.payment_id, txn.user_id
    try:
        items = rzp.fetch_order_payments(txn.provider_order_id)
        pick = (next((i for i in items if i.get('status') == 'captured'), None)
                or next((i for i in items if i.get('status') == 'authorized'), None)
                or (items[0] if items else None))
        if pick:
            apply_gateway_payment(txn, pick, source)
        else:
            txn.last_reconciled_at = utcnow()
            db.session.add(Reconciliation(payment_id=pid, source=source, status_before=txn.status,
                                          status_after=txn.status, gateway_status='no_attempts',
                                          result=ReconResult.MATCHED, note='No payment attempts on this order yet.'))
    except rzp.RazorpayError as e:
        db.session.rollback()
        record_exception(pid, uid, source, 'GATEWAY_ERROR', str(e))
        raise
    except ValueError as e:
        db.session.rollback()
        record_exception(pid, uid, source, 'GATEWAY_DATA_MISMATCH', f'Gateway data rejected: {e}')
        raise


# ── Bills ───────────────────────────────────────────────────────────────────

@ns.route('')
class BillsList(Resource):
    @ns.doc(description='Current bill for each card, plus the payment-provider status.')
    @customer_required
    def get(self):
        user = current_user()
        cards = (LinkedCards.query.filter_by(user_id=user.user_id, is_active=True)
                 .order_by(LinkedCards.due_date.is_(None), LinkedCards.due_date.asc()).all())
        bills = []
        for c in cards:
            f = svc.financials(c)
            bills.append({
                'card_id': c.public_id, 'card_nickname': c.card_nickname, 'issuer_name': c.issuer_name,
                'issuer_code': c.issuer.code if c.issuer else None,
                'gradient': [c.issuer.gradient_from, c.issuer.gradient_to] if c.issuer else None,
                'masked_number': f'•••• {c.last_four_digits}', 'card_source': c.card_source,
                'source_label': svc.SOURCE_LABELS.get(c.card_source),
                'outstanding_balance': f['outstanding_balance'], 'minimum_amount_due': f['minimum_amount_due'],
                'due_date': f['due_date'], 'bill_status': f['bill_status'],
                'paid_in_app_this_cycle': f['paid_in_app_this_cycle'], 'data_as_of': f['data_as_of'],
                'is_stale': f['is_stale'],
            })
        cfg = rzp.payment_config()
        cfg.pop('key_id', None)
        return ok({'bills': bills, 'payment': cfg})


# ── Payment session ─────────────────────────────────────────────────────────

@ns.route('/payment-session')
class PaymentSession(Resource):
    @ns.doc(description='Create a Razorpay order for a card bill payment. Idempotent per idempotency_key, '
                        'so a double-click never creates two payments.')
    @limiter.limit('10 per minute')
    @customer_required
    def post(self):
        try:
            user = current_user()
            cfg = rzp.payment_config()
            if not cfg['configured']:
                return fail(cfg['message'] or 'Payment integration not configured.', 503,
                            code='PAYMENT_NOT_CONFIGURED')
            body = _json()
            v = Validator()
            amount, e = validate_amount(body.get('amount'), 'Payment amount', required=True, allow_zero=False)
            v.check('amount', e)
            key, e = validate_idempotency_key(body.get('idempotency_key'))
            v.check('idempotency_key', e)
            card = svc.owned_card(user.user_id, str(body.get('card_id') or ''))
            if not card:
                return fail('Card not found.', 404, code='NOT_FOUND')
            if not v.ok:
                return v.response()

            existing = PaymentTransactions.query.filter_by(user_id=user.user_id, idempotency_key=key).first()
            if existing:
                if existing.card_id != card.card_id or Decimal(existing.amount) != amount:
                    return fail('This request key was already used for a different payment.', 409,
                                code='IDEMPOTENCY_CONFLICT')
                return ok(_checkout_payload(existing, cfg, card))

            limit_max = get_setting('MAX_CARD_PAYMENT_INR', Decimal(current_app.config['MAX_CARD_PAYMENT_INR']))
            limit_min = get_setting('MIN_CARD_PAYMENT_INR', MIN_PAYMENT)
            if amount < limit_min:
                v.check('amount', f'Minimum payment is ₹{money(limit_min)}.')
            elif amount > limit_max:
                v.check('amount', f'Maximum payment is ₹{money(limit_max)}.')
            elif card.outstanding_balance is not None:
                remaining = Decimal(card.outstanding_balance) - svc.paid_in_app_since(card, card.statement_date)
                if remaining <= 0:
                    v.check('amount', 'There are no dues left on this card for the current cycle.')
                elif amount > remaining:
                    v.check('amount', f'Amount cannot exceed the outstanding ₹{money(remaining)}.')
            if not v.ok:
                return v.response()

            txn = PaymentTransactions(
                user_id=user.user_id, card_id=card.card_id, amount=amount, currency='INR',
                provider='RAZORPAY', provider_mode=cfg['mode'], idempotency_key=key,
                receipt_number=f'CV{utcnow():%y%m%d%H%M%S}{secrets.token_hex(4).upper()}',
                provider_order_id='pending-' + secrets.token_hex(12))
            bill = svc.current_bill(card)
            txn.bill_id = bill.bill_id if bill else None
            db.session.add(txn)
            db.session.flush()       # reserve idempotency key before calling the gateway

            try:
                order = rzp.create_order(int(amount * 100), txn.receipt_number,
                                         {'payment_ref': txn.public_id, 'purpose': 'CREDIT_CARD_BILL'})
            except rzp.RazorpayError as re:
                db.session.rollback()
                record_exception(None, user.user_id, 'CREATE_ORDER', 'GATEWAY_ERROR', str(re))
                return fail(str(re), 502, code='PAYMENT_PROVIDER_ERROR')
            if order.get('amount') != int(amount * 100) or not order.get('id'):
                db.session.rollback()
                return fail('Payment provider returned an unexpected order.', 502, code='PAYMENT_PROVIDER_ERROR')

            txn.provider_order_id = order['id']
            db.session.commit()
            audit('PAYMENT_SESSION_CREATED', user.user_id, 'PAYMENT', txn.public_id,
                  details={'amount': str(amount), 'mode': cfg['mode']})
            return ok(_checkout_payload(txn, cfg, card), 201)
        except IntegrityError:
            db.session.rollback()
            return fail('Duplicate payment request.', 409, code='IDEMPOTENCY_CONFLICT')
        except Exception:
            db.session.rollback()
            return server_error(logger, 'bills/payment-session')


def _checkout_payload(txn, cfg, card):
    return {
        'payment': serialize_payment(txn),
        'checkout': {
            'key': cfg['key_id'], 'order_id': txn.provider_order_id,
            'amount': int(Decimal(txn.amount) * 100), 'currency': txn.currency,
            'name': current_app.config['APP_NAME'],
            'description': f'{card.issuer_name} card •••• {card.last_four_digits} bill payment',
        },
        'mode': cfg['mode'],
        'notice': cfg['message'],
    }


# ── Payment verification ────────────────────────────────────────────────────

@ns.route('/payment-verify')
class PaymentVerify(Resource):
    @ns.doc(description='Called after Razorpay Checkout returns. Verifies the signature, then confirms the '
                        'payment server-to-server before changing its status.')
    @limiter.limit('20 per minute')
    @customer_required
    def post(self):
        try:
            user = current_user()
            body = _json()
            order_id = str(body.get('razorpay_order_id') or '')[:64]
            payment_id = str(body.get('razorpay_payment_id') or '')[:64]
            signature = str(body.get('razorpay_signature') or '')[:128]
            txn = PaymentTransactions.query.filter_by(provider_order_id=order_id, user_id=user.user_id).first()
            if not txn:
                return fail('Payment not found.', 404, code='NOT_FOUND')
            if txn.status == PaymentStatus.SUCCESS:
                return ok({'payment': serialize_payment(txn)})
            if not rzp.verify_checkout_signature(order_id, payment_id, signature):
                record_exception(txn.payment_id, user.user_id, 'VERIFY', 'BAD_SIGNATURE',
                                 'Checkout signature did not verify; status left unchanged.')
                audit('PAYMENT_VERIFY', user.user_id, 'PAYMENT', txn.public_id, status='FAILED',
                      details={'reason': 'bad_signature'})
                return fail('Payment could not be verified.', 400, code='INVALID_SIGNATURE')
            try:
                entity = rzp.fetch_payment(payment_id)
                apply_gateway_payment(txn, entity, 'API_FETCH')
            except rzp.RazorpayError as re:
                db.session.rollback()
                record_exception(txn.payment_id, user.user_id, 'VERIFY', 'GATEWAY_ERROR', f'Could not confirm payment: {re}')
                # Signature was fine but we could not confirm — leave it pending; webhook/reconcile will settle it.
                txn.status = PaymentStatus.PENDING if txn.status == PaymentStatus.CREATED else txn.status
                db.session.commit()
                return ok({'payment': serialize_payment(txn),
                           'message': 'Payment received; confirmation is pending with the provider.'}, 202)
            except ValueError as ve:
                db.session.rollback()
                logger.error(f'[bills/verify] gateway data mismatch: {ve}')
                record_exception(txn.payment_id, user.user_id, 'VERIFY', 'GATEWAY_DATA_MISMATCH', f'Gateway data rejected: {ve}')
                audit('PAYMENT_VERIFY', user.user_id, 'PAYMENT', txn.public_id, status='FAILED',
                      details={'reason': 'mismatch'})
                return fail('Payment details did not match this order.', 400, code='PAYMENT_MISMATCH')
            db.session.commit()
            audit('PAYMENT_VERIFY', user.user_id, 'PAYMENT', txn.public_id, details={'status': txn.status})
            return ok({'payment': serialize_payment(txn)})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'bills/payment-verify')


@ns.route('/webhook')
class RazorpayWebhook(Resource):
    @ns.doc(description='Razorpay webhook (payment.captured / payment.authorized / payment.failed). '
                        'Requires a valid X-Razorpay-Signature.')
    @limiter.limit('300 per minute')
    def post(self):
        raw = request.get_data(cache=True)
        if not rzp.verify_webhook_signature(raw, request.headers.get('X-Razorpay-Signature', '')):
            return fail('Invalid signature.', 401, code='INVALID_SIGNATURE')
        try:
            payload = request.get_json(silent=True) or {}
            event = payload.get('event', '')
            entity = ((payload.get('payload') or {}).get('payment') or {}).get('entity') or {}
            if event in ('payment.captured', 'payment.authorized', 'payment.failed') and entity.get('order_id'):
                txn = PaymentTransactions.query.filter_by(provider_order_id=entity['order_id']).first()
                if txn:
                    try:
                        apply_gateway_payment(txn, entity, 'WEBHOOK')
                        db.session.commit()
                        audit('PAYMENT_WEBHOOK', txn.user_id, 'PAYMENT', txn.public_id,
                              details={'event': event, 'status': txn.status})
                    except ValueError as ve:
                        db.session.rollback()
                        logger.error(f'[bills/webhook] rejected {event}: {ve}')
                        record_exception(txn.payment_id, txn.user_id, 'WEBHOOK', 'GATEWAY_DATA_MISMATCH',
                                         f'Webhook {event} rejected: {ve}')
            return ok({'received': True})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'bills/webhook')


# ── Payment history ─────────────────────────────────────────────────────────

@ns.route('/payments')
class Payments(Resource):
    @ns.doc(description='Payment history.', params={'page': 'Page', 'per_page': 'Max 50'})
    @customer_required
    def get(self):
        page = max(request.args.get('page', 1, type=int), 1)
        per_page = min(max(request.args.get('per_page', 20, type=int), 1), 50)
        p = (PaymentTransactions.query.filter_by(user_id=current_user().user_id)
             .order_by(PaymentTransactions.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False))
        return ok({'payments': [serialize_payment(x) for x in p.items], 'page': page, 'pages': p.pages, 'total': p.total})


@ns.route('/payments/<string:payment_id>')
class Payment(Resource):
    @ns.doc(description='One payment (owner only). Open payments are reconciled with Razorpay on read.')
    @limiter.limit('60 per minute')
    @customer_required
    def get(self, payment_id):
        try:
            txn = PaymentTransactions.query.filter_by(public_id=payment_id[:32], user_id=current_user().user_id).first()
            if not txn:
                return fail('Payment not found.', 404, code='NOT_FOUND')
            if (txn.status in PaymentStatus.OPEN or txn.status == PaymentStatus.FAILED) and \
                    not txn.provider_order_id.startswith('pending-') and \
                    (txn.last_reconciled_at is None or utcnow() - txn.last_reconciled_at > RECONCILE_INTERVAL) and \
                    utcnow() - txn.created_at < timedelta(days=2):
                try:
                    reconcile(txn)
                    db.session.commit()
                except (rzp.RazorpayError, ValueError) as e:
                    db.session.rollback()
                    logger.warning(f'[bills/payment] reconcile skipped: {e.__class__.__name__}')
            return ok({'payment': serialize_payment(txn)})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'bills/payment')
