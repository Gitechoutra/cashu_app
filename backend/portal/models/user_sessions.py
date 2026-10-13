from portal import db
from .base import CrudMixin, utcnow, new_public_id


class SessionStatus:
    ACTIVE = 'ACTIVE'
    REVOKED = 'REVOKED'
    EXPIRED = 'EXPIRED'


class UserSessions(CrudMixin, db.Model):
    """One row per signed-in device. The refresh token itself is never stored —
    only its SHA-256, so a database leak cannot be replayed as a login."""
    __tablename__ = 'user_sessions'

    session_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    device_binding_id = db.Column(db.Integer, db.ForeignKey('device_bindings.device_binding_id'), nullable=True, index=True)

    refresh_token_hash = db.Column(db.String(64), unique=True, nullable=False)
    # Previous token after rotation — presenting it again signals theft.
    previous_refresh_hash = db.Column(db.String(64), nullable=True, index=True)

    status = db.Column(db.String(20), nullable=False, default=SessionStatus.ACTIVE)
    revoked_reason = db.Column(db.String(50), nullable=True)

    last_active_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    # Pending WebAuthn challenge for this device (single-use, short-lived).
    webauthn_challenge = db.Column(db.String(128), nullable=True)
    webauthn_challenge_expires = db.Column(db.DateTime, nullable=True)

    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_on = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship('Users', back_populates='sessions')
