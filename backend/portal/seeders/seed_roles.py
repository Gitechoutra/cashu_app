"""Seeds the three access roles. Idempotent."""

from portal import db
from portal.models.roles import Roles, RoleName

ROLES = [
    (RoleName.ADMIN, 'Admin', 'Full platform administration: users, roles, gateways, banks, audit.'),
    (RoleName.SUPPORT, 'Customer Support', 'Handles support tickets; read-only, masked view of customer data.'),
    (RoleName.USER, 'User', 'Customer — manages their own cards, bills and payments.'),
]


def seed_roles():
    existing = {r for (r,) in db.session.query(Roles.role_name).all()}
    added = 0
    for name, display, desc in ROLES:
        if name not in existing:
            db.session.add(Roles(role_name=name, display_name=display, description=desc))
            added += 1
    db.session.commit()
    return added
