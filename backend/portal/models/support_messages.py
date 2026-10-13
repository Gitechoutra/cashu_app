from portal import db
from .base import CrudMixin, utcnow


class SupportMessages(CrudMixin, db.Model):
    __tablename__ = 'support_messages'

    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.ticket_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    sender_role = db.Column(db.String(20), nullable=False)          # USER | SUPPORT | ADMIN
    body = db.Column(db.Text, nullable=False)
    # Internal notes are visible to staff only, never to the customer.
    is_internal = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    ticket = db.relationship('SupportTickets', back_populates='messages')
    sender = db.relationship('Users')
