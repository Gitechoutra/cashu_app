from portal import db
from .base import CrudMixin, utcnow


class OTPPurpose:
    LOGIN = 'LOGIN'          # registration and login share one mobile-OTP flow

    CHOICES = [LOGIN]


class OTPStatus:
    PENDING = 'PENDING'
    VERIFIED = 'VERIFIED'
    EXPIRED = 'EXPIRED'
    FAILED = 'FAILED'
    SUPERSEDED = 'SUPERSEDED'


class OTPVerifications(CrudMixin, db.Model):
    """OTPs are random per request, hashed at rest and single-use."""
    __tablename__ = 'otp_verifications'

    otp_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    mobile_number = db.Column(db.String(16), nullable=False, index=True)
    otp_hash = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(30), nullable=False, default=OTPPurpose.LOGIN)
    status = db.Column(db.String(20), nullable=False, default=OTPStatus.PENDING)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=5)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_on = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
