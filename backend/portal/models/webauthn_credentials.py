from portal import db
from .base import CrudMixin, utcnow


class WebAuthnCredentials(CrudMixin, db.Model):
    """Device biometric (fingerprint / Face ID) keys. Only the public key is
    stored — the biometric itself never leaves the user's device."""
    __tablename__ = 'webauthn_credentials'

    credential_pk = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    credential_id = db.Column(db.String(512), unique=True, nullable=False)   # base64url
    public_key = db.Column(db.Text, nullable=False)                          # base64url COSE key
    sign_count = db.Column(db.BigInteger, nullable=False, default=0)
    label = db.Column(db.String(60), nullable=True)
    created_on = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_used_on = db.Column(db.DateTime, nullable=True)

    user = db.relationship('Users', back_populates='webauthn_credentials')
