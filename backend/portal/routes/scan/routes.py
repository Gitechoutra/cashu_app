"""Scan & Pay history. The browser reports a UPI QR it handed to the user's UPI
app; the server re-validates it. CardVault never learns (or claims) the outcome."""

import re
from decimal import Decimal, InvalidOperation

from flask import request
from flask_restx import Resource

from portal import db
from portal.extensions import limiter
from portal.helpers.auth import current_user, customer_required
from portal.helpers.card_math import money
from portal.helpers.responses import fail, ok
from portal.helpers.validators import clean_text
from portal.models.base import iso
from portal.models.qr_payments import QrPayments, QrPaymentStatus

from . import ns, logger

VPA_RE = re.compile(r'^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z][a-zA-Z0-9]{1,63}$')


def serialize(q):
    return {'id': q.public_id, 'payee_vpa': q.payee_vpa, 'payee_name': q.payee_name,
            'is_merchant': bool(q.merchant_code), 'amount': money(q.amount), 'note': q.note,
            'status': q.status, 'created_at': iso(q.created_at)}


@ns.route('/payments')
class ScanPayments(Resource):
    @ns.doc(description='Recent Scan & Pay hand-offs.')
    @customer_required
    def get(self):
        rows = (QrPayments.query.filter_by(user_id=current_user().user_id)
                .order_by(QrPayments.created_at.desc()).limit(20).all())
        return ok({'payments': [serialize(r) for r in rows]})

    @ns.doc(description='Record that a scanned UPI payment was handed to the UPI app.')
    @limiter.limit('60 per hour')
    @customer_required
    def post(self):
        body = request.get_json(silent=True) or {}
        vpa = str(body.get('payee_vpa') or '').strip()
        if not VPA_RE.match(vpa):
            return fail('Invalid UPI ID.', 400, code='VALIDATION_ERROR')
        amount = None
        if body.get('amount') not in (None, ''):
            try:
                amount = Decimal(str(body['amount']))
            except InvalidOperation:
                return fail('Invalid amount.', 400, code='VALIDATION_ERROR')
            if amount <= 0 or amount > Decimal('10000000') or amount != amount.quantize(Decimal('0.01')):
                return fail('Invalid amount.', 400, code='VALIDATION_ERROR')
        q = QrPayments(user_id=current_user().user_id, payee_vpa=vpa,
                       payee_name=clean_text(body.get('payee_name'))[:80] or None,
                       merchant_code=re.sub(r'\D', '', str(body.get('merchant_code') or ''))[:10] or None,
                       amount=amount, note=clean_text(body.get('note'))[:80] or None,
                       status=QrPaymentStatus.HANDED_OFF)
        db.session.add(q)
        db.session.commit()
        return ok({'payment': serialize(q)}, 201)
