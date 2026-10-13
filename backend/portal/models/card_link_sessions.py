from portal import db
from .base import CrudMixin, utcnow, new_public_id


class LinkSessionStatus:
    CREATED = 'CREATED'
    AWAITING_USER = 'AWAITING_USER'       # user sent to the provider's consent screen
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    EXPIRED = 'EXPIRED'

    TERMINAL = [COMPLETED, FAILED, EXPIRED]


class CardLinkSessions(CrudMixin, db.Model):
    """Binds a provider linking attempt to the user who started it. The callback
    is accepted only with the matching single-use `state` (stored hashed)."""
    __tablename__ = 'card_link_sessions'

    link_session_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    issuer_id = db.Column(db.Integer, db.ForeignKey('card_issuers.issuer_id'), nullable=False)
    provider_name = db.Column(db.String(50), nullable=False)

    state_hash = db.Column(db.String(64), unique=True, nullable=False)
    provider_session_ref = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=LinkSessionStatus.CREATED)

    consent_id = db.Column(db.Integer, db.ForeignKey('financial_consents.consent_id'), nullable=True)
    cards_linked = db.Column(db.Integer, nullable=False, default=0)
    error_code = db.Column(db.String(40), nullable=True)
    error_message = db.Column(db.String(255), nullable=True)

    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
