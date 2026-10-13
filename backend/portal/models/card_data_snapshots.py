from portal import db
from .base import CrudMixin, utcnow


class CardDataSnapshots(CrudMixin, db.Model):
    """Point-in-time copy of a card's figures with their provenance, written on
    every create / edit / provider refresh."""
    __tablename__ = 'card_data_snapshots'

    snapshot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    card_id = db.Column(db.Integer, db.ForeignKey('linked_cards.card_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)

    source = db.Column(db.String(20), nullable=False)          # CardSource.*
    provider_name = db.Column(db.String(50), nullable=True)

    credit_limit = db.Column(db.Numeric(14, 2), nullable=True)
    outstanding_balance = db.Column(db.Numeric(14, 2), nullable=True)
    available_credit = db.Column(db.Numeric(14, 2), nullable=True)
    minimum_amount_due = db.Column(db.Numeric(14, 2), nullable=True)
    statement_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)

    data_as_of = db.Column(db.DateTime, nullable=False)
    captured_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    note = db.Column(db.String(100), nullable=True)

    card = db.relationship('LinkedCards', back_populates='snapshots')
