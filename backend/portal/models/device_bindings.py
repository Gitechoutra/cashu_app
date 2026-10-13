from portal import db
from .base import CrudMixin, utcnow, new_public_id


class DeviceBindings(CrudMixin, db.Model):
    """Devices a user has signed in from. The browser keeps a random device id
    (X-Device-Id header); only its SHA-256 is stored."""
    __tablename__ = 'device_bindings'
    __table_args__ = (db.UniqueConstraint('user_id', 'device_hash', name='uq_device_user_hash'),)

    device_binding_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    device_hash = db.Column(db.String(64), nullable=False)
    device_name = db.Column(db.String(80), nullable=True)
    first_seen_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_ip = db.Column(db.String(64), nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
