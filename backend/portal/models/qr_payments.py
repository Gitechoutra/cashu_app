from portal import db
from .base import CrudMixin, utcnow, new_public_id


class QrPaymentStatus:
    HANDED_OFF = 'HANDED_OFF'      # sent to the user's UPI app; the outcome happens there, not in CardVault


class QrPayments(CrudMixin, db.Model):
    """Scan & Pay history. CardVault does not execute UPI payments, so this records
    what was scanned and handed to the UPI app - never a success/failure it cannot know."""
    __tablename__ = 'qr_payments'

    qr_payment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    payee_vpa = db.Column(db.String(256), nullable=False)
    payee_name = db.Column(db.String(80), nullable=True)
    merchant_code = db.Column(db.String(10), nullable=True)
    amount = db.Column(db.Numeric(14, 2), nullable=True)
    note = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=QrPaymentStatus.HANDED_OFF)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
