from portal import db
from .base import CrudMixin, utcnow


class SettingType:
    INT = 'INT'
    DECIMAL = 'DECIMAL'
    STRING = 'STRING'
    BOOL = 'BOOL'


class AdminSettings(CrudMixin, db.Model):
    """Platform settings editable from Admin -> Platform settings.
    Defaults are seeded by portal/seeders/seed_admin_settings.py."""
    __tablename__ = 'admin_settings'

    setting_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(60), unique=True, nullable=False)
    value = db.Column(db.String(500), nullable=True)
    value_type = db.Column(db.String(10), nullable=False, default=SettingType.STRING)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_public = db.Column(db.Boolean, nullable=False, default=False)      # readable by the app without auth
    updated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
