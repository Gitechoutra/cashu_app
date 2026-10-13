from portal import db
from .base import CrudMixin, utcnow


class CardIssuers(CrudMixin, db.Model):
    """Configurable list of issuing banks shown in the Add Card flow.
    Seeded by portal/seeders/seed_card_issuers.py; add rows to support more banks."""
    __tablename__ = 'card_issuers'

    issuer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(30), nullable=False)
    gradient_from = db.Column(db.String(9), nullable=False, default='#1E293B')
    gradient_to = db.Column(db.String(9), nullable=False, default='#0F172A')
    # Institution id at the configured data provider (e.g. an AA FIP id).
    # NULL means this bank is not linkable through the current provider.
    provider_institution_id = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)
    created_on = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {
            'issuer_id': self.issuer_id,
            'code': self.code,
            'name': self.name,
            'short_name': self.short_name,
            'gradient': [self.gradient_from, self.gradient_to],
            # Top grid in the Add Card picker (see seed_card_issuers.POPULAR_CUTOFF).
            'popular': self.sort_order < 9,
        }
