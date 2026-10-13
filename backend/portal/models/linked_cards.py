from portal import db
from .base import CrudMixin, utcnow, new_public_id


class CardSource:
    USER_ENTERED = 'USER_ENTERED'   # typed in by the user — never bank verified
    PROVIDER = 'PROVIDER'           # retrieved from an authorised data provider
    SAMPLE = 'SAMPLE'               # test fixtures only — never shown as real

    CHOICES = [USER_ENTERED, PROVIDER, SAMPLE]


class VerificationStatus:
    UNVERIFIED = 'UNVERIFIED'
    VERIFIED = 'VERIFIED'
    CONSENT_EXPIRED = 'CONSENT_EXPIRED'
    CONSENT_REVOKED = 'CONSENT_REVOKED'
    SAMPLE = 'SAMPLE'


class LinkedCards(CrudMixin, db.Model):
    """A user's credit card. Only the last four digits are ever stored — never
    the full number, CVV, expiry, PIN or bank credentials."""
    __tablename__ = 'linked_cards'
    __table_args__ = (
        db.CheckConstraint('credit_limit IS NULL OR credit_limit >= 0', name='ck_cards_limit_nonneg'),
        db.CheckConstraint('minimum_amount_due IS NULL OR minimum_amount_due >= 0', name='ck_cards_min_due_nonneg'),
        db.CheckConstraint('billing_day IS NULL OR (billing_day >= 1 AND billing_day <= 31)', name='ck_cards_billing_day'),
    )

    card_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    issuer_id = db.Column(db.Integer, db.ForeignKey('card_issuers.issuer_id'), nullable=True)

    issuer_name = db.Column(db.String(100), nullable=False)
    card_nickname = db.Column(db.String(40), nullable=False)
    card_network = db.Column(db.String(20), db.ForeignKey('card_networks.code'), nullable=True)
    last_four_digits = db.Column(db.String(4), nullable=False)

    card_source = db.Column(db.String(20), nullable=False, default=CardSource.USER_ENTERED)
    verification_status = db.Column(db.String(20), nullable=False, default=VerificationStatus.UNVERIFIED)

    # Money is DECIMAL(14,2) — never float.
    credit_limit = db.Column(db.Numeric(14, 2), nullable=True)
    outstanding_balance = db.Column(db.Numeric(14, 2), nullable=True)   # negative = credit balance (provider only)
    available_credit = db.Column(db.Numeric(14, 2), nullable=True)      # as reported; NULL when unknown
    minimum_amount_due = db.Column(db.Numeric(14, 2), nullable=True)
    billing_day = db.Column(db.SmallInteger, nullable=True)             # statement day of month
    statement_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    currency = db.Column(db.String(3), nullable=False, default='INR')

    provider_name = db.Column(db.String(50), nullable=True)
    provider_reference = db.Column(db.String(128), nullable=True)       # opaque provider account ref
    consent_id = db.Column(db.Integer, db.ForeignKey('financial_consents.consent_id'), nullable=True)

    data_as_of = db.Column(db.DateTime, nullable=False, default=utcnow)  # when the figures were true
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    removed_at = db.Column(db.DateTime, nullable=True)
    # "<user>:<issuer>:<last4>" while active, NULL once removed — a unique index
    # that blocks duplicates but lets a removed card be re-added.
    dedupe_key = db.Column(db.String(120), unique=True, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship('Users', back_populates='cards')
    issuer = db.relationship('CardIssuers')
    consent = db.relationship('FinancialConsents')
    snapshots = db.relationship('CardDataSnapshots', back_populates='card', lazy='dynamic',
                                cascade='all, delete-orphan')

    @staticmethod
    def build_dedupe_key(user_id, issuer_name, last_four):
        return f'{user_id}:{(issuer_name or "").strip().upper()[:80]}:{last_four}'
