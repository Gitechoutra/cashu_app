from portal import db
from .base import CrudMixin, utcnow, new_public_id


class Bills(CrudMixin, db.Model):
    """The current statement for a card. For manual cards it mirrors the
    user-entered figures; for linked cards it comes from the provider.
    Status is derived (see helpers/card_math.bill_status), not stored."""
    __tablename__ = 'bills'
    __table_args__ = (
        db.UniqueConstraint('card_id', 'due_date', name='uq_bill_card_due'),
    )

    bill_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    card_id = db.Column(db.Integer, db.ForeignKey('linked_cards.card_id'), nullable=False, index=True)

    statement_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    total_amount_due = db.Column(db.Numeric(14, 2), nullable=True)
    minimum_amount_due = db.Column(db.Numeric(14, 2), nullable=True)
    source = db.Column(db.String(20), nullable=False)
    is_current = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    card = db.relationship('LinkedCards')
