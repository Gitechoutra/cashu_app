from portal import db
from .base import CrudMixin, utcnow


class KycStatus:
    NOT_STARTED = 'NOT_STARTED'
    PENDING = 'PENDING'
    VERIFIED = 'VERIFIED'
    REJECTED = 'REJECTED'

    CHOICES = [NOT_STARTED, PENDING, VERIFIED, REJECTED]


class KycVerifications(CrudMixin, db.Model):
    """KYC status per user. Identity documents (PAN / Aadhaar numbers, images) are
    NOT stored here - only the licensed e-KYC provider's reference and outcome."""
    __tablename__ = 'kyc_verifications'

    kyc_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), unique=True, nullable=False)
    status = db.Column(db.String(15), nullable=False, default=KycStatus.NOT_STARTED)
    method = db.Column(db.String(30), nullable=True)                 # e.g. DIGILOCKER, CKYC, VIDEO_KYC
    provider_name = db.Column(db.String(50), nullable=True)
    provider_reference = db.Column(db.String(128), nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
