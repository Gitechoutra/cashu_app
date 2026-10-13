"""Card networks referenced by linked_cards.card_network. Idempotent.
(The migration also inserts these so the foreign key can be added safely.)"""

from portal import db
from portal.models.card_networks import CardNetworks

NETWORKS = [('VISA', 'Visa', 1), ('MASTERCARD', 'Mastercard', 2), ('RUPAY', 'RuPay', 3),
            ('AMEX', 'American Express', 4), ('DINERS', 'Diners Club', 5), ('OTHER', 'Other', 99)]


def seed_card_networks():
    existing = {c for (c,) in db.session.query(CardNetworks.code).all()}
    added = 0
    for code, name, order in NETWORKS:
        if code not in existing:
            db.session.add(CardNetworks(code=code, name=name, sort_order=order, is_active=True))
            added += 1
    db.session.commit()
    return added
