from portal import db
from .base import CrudMixin, utcnow, new_public_id


class ConsentStatus:
    PENDING = 'PENDING'
    ACTIVE = 'ACTIVE'
    REJECTED = 'REJECTED'
    EXPIRED = 'EXPIRED'
    REVOKED = 'REVOKED'


class FinancialConsents(CrudMixin, db.Model):
    """User consent granted to an authorised data provider (e.g. an RBI Account
    Aggregator). Provider tokens are encrypted at rest and never sent to the browser."""
    __tablename__ = 'financial_consents'

    consent_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)

    provider_name = db.Column(db.String(50), nullable=False)
    consent_reference = db.Column(db.String(128), nullable=True, index=True)  # provider's consent handle
    purpose = db.Column(db.String(255), nullable=False)
    data_scope = db.Column(db.JSON, nullable=True)       # e.g. ["credit_limit", "outstanding_balance"]
    status = db.Column(db.String(20), nullable=False, default=ConsentStatus.PENDING)

    encrypted_access_token = db.Column(db.Text, nullable=True)   # Fernet ciphertext
    token_expires_at = db.Column(db.DateTime, nullable=True)
    consent_expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)
