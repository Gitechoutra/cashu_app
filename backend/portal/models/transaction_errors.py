from portal import db
from .base import CrudMixin, utcnow


class TransactionErrors(CrudMixin, db.Model):
    """Payment exceptions for Admin review. Never contains secrets, signatures or card data."""
    __tablename__ = 'transaction_errors'

    error_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment_transactions.payment_id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True, index=True)
    stage = db.Column(db.String(20), nullable=False)          # CREATE_ORDER | VERIFY | WEBHOOK | RECONCILE
    error_code = db.Column(db.String(40), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_resolved = db.Column(db.Boolean, nullable=False, default=False, index=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
