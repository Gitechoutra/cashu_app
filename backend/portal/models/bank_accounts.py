from portal import db
from .base import CrudMixin, utcnow, new_public_id


class BankAccountVerification:
    UNVERIFIED = 'UNVERIFIED'      # entered by the user; ownership not confirmed
    VERIFIED = 'VERIFIED'          # confirmed by a penny-drop / account-validation provider


class BankAccounts(CrudMixin, db.Model):
    """User's own bank accounts (for future AutoPay / refunds). The full account
    number is Fernet-encrypted; only the last 4 digits are ever returned."""
    __tablename__ = 'bank_accounts'
    __table_args__ = (db.UniqueConstraint('user_id', 'account_fingerprint', name='uq_bank_account_user'),)

    bank_account_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    account_holder_name = db.Column(db.String(100), nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    ifsc = db.Column(db.String(11), nullable=False)
    account_number_encrypted = db.Column(db.Text, nullable=False)
    account_last4 = db.Column(db.String(4), nullable=False)
    account_fingerprint = db.Column(db.String(64), nullable=False)   # HMAC for duplicate detection
    account_type = db.Column(db.String(10), nullable=False, default='SAVINGS')
    verification_status = db.Column(db.String(12), nullable=False, default=BankAccountVerification.UNVERIFIED)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
