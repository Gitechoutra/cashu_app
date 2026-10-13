from portal import db
from .base import CrudMixin, utcnow


class CardTransactions(CrudMixin, db.Model):
    """Card statement transactions — written ONLY from an authorised provider
    response. Manual cards never have rows here."""
    __tablename__ = 'card_transactions'
    __table_args__ = (
        db.UniqueConstraint('card_id', 'provider_txn_ref', name='uq_card_txn_ref'),
    )

    txn_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    card_id = db.Column(db.Integer, db.ForeignKey('linked_cards.card_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    provider_txn_ref = db.Column(db.String(128), nullable=False)
    txn_date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    txn_type = db.Column(db.String(10), nullable=False)        # DEBIT | CREDIT
    txn_status = db.Column(db.String(10), nullable=False, default='POSTED')  # POSTED | PENDING
    source = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
