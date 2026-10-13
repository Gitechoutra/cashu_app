from portal import db
from .base import CrudMixin, utcnow, new_public_id


class PaymentStatus:
    CREATED = 'CREATED'      # order created, user has not paid yet
    PENDING = 'PENDING'      # payment authorised / awaiting capture or confirmation
    SUCCESS = 'SUCCESS'      # captured — confirmed server-to-server with Razorpay
    FAILED = 'FAILED'

    OPEN = [CREATED, PENDING]


class SettlementStatus:
    """Whether the money reached the card issuer (BBPS). Separate from the
    collection status above — a captured payment is not a paid card bill."""
    NOT_STARTED = 'NOT_STARTED'
    NOT_CONFIGURED = 'NOT_CONFIGURED'     # no BBPS partner — issuer not credited (test mode only)
    PENDING = 'PENDING'
    SETTLED = 'SETTLED'
    FAILED = 'FAILED'


class PaymentTransactions(CrudMixin, db.Model):
    __tablename__ = 'payment_transactions'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'idempotency_key', name='uq_payment_idempotency'),
        db.CheckConstraint('amount > 0', name='ck_payment_amount_pos'),
    )

    payment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    card_id = db.Column(db.Integer, db.ForeignKey('linked_cards.card_id'), nullable=False, index=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.bill_id'), nullable=True)

    amount = db.Column(db.Numeric(14, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='INR')

    provider = db.Column(db.String(30), nullable=False, default='RAZORPAY')
    provider_mode = db.Column(db.String(10), nullable=False, default='test')   # test | live
    provider_order_id = db.Column(db.String(64), unique=True, nullable=False)
    provider_payment_id = db.Column(db.String(64), unique=True, nullable=True)
    payment_method = db.Column(db.String(30), nullable=True)

    status = db.Column(db.String(20), nullable=False, default=PaymentStatus.CREATED, index=True)
    settlement_status = db.Column(db.String(20), nullable=False, default=SettlementStatus.NOT_STARTED)
    verified_via = db.Column(db.String(30), nullable=True)    # API_FETCH | WEBHOOK
    failure_reason = db.Column(db.String(255), nullable=True)

    idempotency_key = db.Column(db.String(64), nullable=False)
    receipt_number = db.Column(db.String(40), unique=True, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_reconciled_at = db.Column(db.DateTime, nullable=True)

    card = db.relationship('LinkedCards')
