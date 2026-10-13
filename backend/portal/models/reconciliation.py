from portal import db
from .base import CrudMixin, utcnow


class ReconResult:
    MATCHED = 'MATCHED'        # our status already agreed with the gateway
    UPDATED = 'UPDATED'        # our status was corrected from the gateway's
    MISMATCH = 'MISMATCH'      # gateway data did not match the order (amount / order id) - not applied
    ERROR = 'ERROR'            # gateway unreachable / rejected the request


class Reconciliation(CrudMixin, db.Model):
    """One row per check of a payment against the gateway (verify, webhook, poll or admin run)."""
    __tablename__ = 'reconciliation'

    recon_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment_transactions.payment_id'), nullable=False, index=True)
    source = db.Column(db.String(20), nullable=False)          # API_FETCH | WEBHOOK | RECONCILE | ADMIN_RUN
    status_before = db.Column(db.String(20), nullable=True)
    status_after = db.Column(db.String(20), nullable=True)
    gateway_status = db.Column(db.String(20), nullable=True)
    result = db.Column(db.String(10), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
