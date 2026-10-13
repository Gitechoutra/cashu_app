from portal import db
from .base import CrudMixin, utcnow, new_public_id


class UserStatus:
    ACTIVE = 'ACTIVE'
    SUSPENDED = 'SUSPENDED'

    CHOICES = [ACTIVE, SUSPENDED]


class Users(CrudMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), nullable=False, index=True)
    # Set for staff accounts defined in seeders/seed_admin.py / seed_customersupport.py.
    # Those files are the source of truth for the account's mobile, name, PIN and role.
    seed_key = db.Column(db.String(40), unique=True, nullable=True)

    # E.164, e.g. +919876543210 — verified by SMS OTP at registration/login.
    mobile_number = db.Column(db.String(16), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=UserStatus.ACTIVE)

    # App PIN — only a salted hash (werkzeug scrypt/pbkdf2) is stored.
    pin_hash = db.Column(db.String(255), nullable=True)
    pin_set_at = db.Column(db.DateTime, nullable=True)
    pin_failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    # Staff (Admin / Customer Support) sign in with email + 6-digit PIN instead of OTP.
    email = db.Column(db.String(254), unique=True, nullable=True)
    pin_locked_until = db.Column(db.DateTime, nullable=True)          # set after too many wrong PINs
    pin_reset_required = db.Column(db.Boolean, nullable=False, default=False)  # temporary PIN from an Admin

    last_login = db.Column(db.DateTime, nullable=True)
    created_on = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_on = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    role = db.relationship('Roles', back_populates='users')
    sessions = db.relationship('UserSessions', back_populates='user', lazy='dynamic')
    webauthn_credentials = db.relationship('WebAuthnCredentials', back_populates='user', lazy='dynamic')
    cards = db.relationship('LinkedCards', back_populates='user', lazy='dynamic')

    @property
    def masked_mobile(self):
        m = self.mobile_number or ''
        return f'{m[:3]} ••••• {m[-4:]}' if len(m) >= 8 else m

    @property
    def role_name(self):
        return self.role.role_name if self.role else None

    def __repr__(self):
        return f'<User {self.user_id}>'
