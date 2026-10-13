from portal import db
from .base import CrudMixin, utcnow


class GatewayProvider:
    RAZORPAY = 'RAZORPAY'

    CHOICES = [RAZORPAY]


class PaymentGateways(CrudMixin, db.Model):
    """Admin-managed payment gateway configuration. Secrets are Fernet-encrypted
    at rest, never returned by any API (only masked), and the active row takes
    precedence over the .env values."""
    __tablename__ = 'payment_gateways'

    gateway_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    provider = db.Column(db.String(30), nullable=False, default=GatewayProvider.RAZORPAY)
    display_name = db.Column(db.String(60), nullable=False)
    mode = db.Column(db.String(10), nullable=False, default='test')        # derived from key id: test | live
    key_id = db.Column(db.String(64), nullable=False)                      # publishable
    encrypted_key_secret = db.Column(db.Text, nullable=False)
    encrypted_webhook_secret = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=False)       # at most one active (enforced in code)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
