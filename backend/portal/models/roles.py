from portal import db
from .base import CrudMixin, utcnow


class RoleName:
    ADMIN = 'ADMIN'
    SUPPORT = 'SUPPORT'          # Customer Support
    USER = 'USER'

    CHOICES = [ADMIN, SUPPORT, USER]
    STAFF = [ADMIN, SUPPORT]


class Roles(CrudMixin, db.Model):
    """Access roles. The server enforces them on every protected endpoint
    (helpers/auth.role_required) — the frontend only chooses which screens to show."""
    __tablename__ = 'roles'

    role_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_name = db.Column(db.String(20), unique=True, nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_on = db.Column(db.DateTime, nullable=False, default=utcnow)

    users = db.relationship('Users', back_populates='role', lazy='dynamic')

    @staticmethod
    def id_for(name):
        r = Roles.query.filter_by(role_name=name).first()
        if r is None:
            raise RuntimeError(f'Role {name} missing — run seeders / migrations.')
        return r.role_id
