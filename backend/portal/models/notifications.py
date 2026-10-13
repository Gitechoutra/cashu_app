from portal import db
from .base import CrudMixin, utcnow, new_public_id


class NotificationType:
    PAYMENT = 'PAYMENT'
    BILL_DUE = 'BILL_DUE'
    SUPPORT = 'SUPPORT'
    SECURITY = 'SECURITY'
    SYSTEM = 'SYSTEM'


class Notifications(CrudMixin, db.Model):
    """In-app notifications. `dedupe_key` stops the same reminder being created twice."""
    __tablename__ = 'notifications'

    notification_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.String(500), nullable=True)
    link = db.Column(db.String(200), nullable=True)          # in-app route, e.g. /user/bills
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    dedupe_key = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
