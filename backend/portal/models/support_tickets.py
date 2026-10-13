from portal import db
from .base import CrudMixin, utcnow, new_public_id


class TicketStatus:
    OPEN = 'OPEN'
    IN_PROGRESS = 'IN_PROGRESS'
    WAITING_ON_USER = 'WAITING_ON_USER'
    RESOLVED = 'RESOLVED'
    CLOSED = 'CLOSED'

    CHOICES = [OPEN, IN_PROGRESS, WAITING_ON_USER, RESOLVED, CLOSED]
    ACTIVE = [OPEN, IN_PROGRESS, WAITING_ON_USER]


class TicketCategory:
    CHOICES = ['CARD', 'PAYMENT', 'ACCOUNT', 'SECURITY', 'OTHER']


class TicketPriority:
    CHOICES = ['LOW', 'NORMAL', 'HIGH', 'URGENT']


class SupportTickets(CrudMixin, db.Model):
    __tablename__ = 'support_tickets'

    ticket_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, default=new_public_id)
    reference = db.Column(db.String(16), unique=True, nullable=False)       # shown to users, e.g. CV-7K2Q9M
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True, index=True)

    subject = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(20), nullable=False, default='OTHER')
    priority = db.Column(db.String(10), nullable=False, default='NORMAL')
    status = db.Column(db.String(20), nullable=False, default=TicketStatus.OPEN, index=True)
    # Optional context the user attached (their own records only).
    card_id = db.Column(db.Integer, db.ForeignKey('linked_cards.card_id'), nullable=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment_transactions.payment_id'), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('Users', foreign_keys=[user_id])
    assignee = db.relationship('Users', foreign_keys=[assigned_to])
    card = db.relationship('LinkedCards')
    payment = db.relationship('PaymentTransactions')
    messages = db.relationship('SupportMessages', back_populates='ticket', lazy='dynamic',
                               order_by='SupportMessages.created_at', cascade='all, delete-orphan')
