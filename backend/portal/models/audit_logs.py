from portal import db
from .base import CrudMixin, utcnow


class AuditLogs(CrudMixin, db.Model):
    """Append-only trail of security- and money-relevant actions.
    Never write OTPs, PINs, tokens, signatures or full card data here."""
    __tablename__ = 'audit_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True, index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    entity_type = db.Column(db.String(40), nullable=True)
    entity_id = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='SUCCESS')
    details = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_on = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
