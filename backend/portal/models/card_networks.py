from portal import db
from .base import CrudMixin


class CardNetworks(CrudMixin, db.Model):
    """Card schemes (Visa, Mastercard, RuPay...). linked_cards.card_network references `code`."""
    __tablename__ = 'card_networks'

    network_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=100)

    def to_dict(self):
        return {'code': self.code, 'name': self.name}
