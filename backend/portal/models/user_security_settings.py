from portal import db
from .base import CrudMixin, utcnow


class UserSecuritySettings(CrudMixin, db.Model):
    """Per-user security preferences. The idle lock can only be made STRICTER
    than the server's SESSION_IDLE_LOCK_MINUTES, never looser."""
    __tablename__ = 'user_security_settings'

    settings_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), unique=True, nullable=False)
    idle_lock_minutes = db.Column(db.SmallInteger, nullable=True)          # NULL = server default
    login_alerts = db.Column(db.Boolean, nullable=False, default=True)     # notify on sign-in from a new device
    payment_alerts = db.Column(db.Boolean, nullable=False, default=True)   # notify on payment success / failure
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
