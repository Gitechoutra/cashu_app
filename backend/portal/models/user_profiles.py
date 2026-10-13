from portal import db
from .base import CrudMixin, utcnow


class UserProfiles(CrudMixin, db.Model):
    """Optional profile details (the mobile number lives on users)."""
    __tablename__ = 'user_profiles'

    profile_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), unique=True, nullable=False)
    email = db.Column(db.String(254), nullable=True)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    city = db.Column(db.String(60), nullable=True)
    state = db.Column(db.String(60), nullable=True)
    preferred_language = db.Column(db.String(5), nullable=False, default='en')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
