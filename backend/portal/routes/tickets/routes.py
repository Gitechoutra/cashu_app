"""Help & Support for customers: raise tickets about their own cards/payments
and chat with Customer Support. Users only ever see their own tickets and
never see staff-internal notes."""

import secrets

from flask import request
from flask_restx import Resource

from portal import db
from portal.extensions import limiter
from portal.helpers import card_service as svc
from portal.helpers.audit import audit
from portal.helpers.auth import current_user, customer_required
from portal.helpers.pagination import paged
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.validators import Validator, clean_text, validate_choice
from portal.models.base import iso, utcnow
from portal.models.payment_transactions import PaymentTransactions
from portal.models.roles import RoleName
from portal.models.support_messages import SupportMessages
from portal.models.support_tickets import SupportTickets, TicketCategory, TicketStatus

from . import ns, logger

MAX_BODY = 2000
MAX_OPEN_TICKETS = 10


def _json():
    return request.get_json(silent=True) or {}


def new_reference():
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    for _ in range(10):
        ref = 'CV-' + ''.join(secrets.choice(alphabet) for _ in range(6))
        if not SupportTickets.query.filter_by(reference=ref).first():
            return ref
    raise RuntimeError('could not allocate ticket reference')


def validate_body(text):
    body = str(text or '').strip()
    if not body:
        return None, 'Message cannot be empty.'
    if len(body) > MAX_BODY:
        return None, f'Message is too long (max {MAX_BODY} characters).'
    return body, None


def serialize_message(m, viewer_is_staff):
    return {'message_id': m.message_id, 'body': m.body, 'is_internal': m.is_internal,
            'from': 'CUSTOMER' if m.sender_role == RoleName.USER else 'SUPPORT',
            'sender_name': (m.sender.full_name if viewer_is_staff or m.sender_role == RoleName.USER
                            else (m.sender.full_name or 'Support').split(' ')[0] + ' (Support)'),
            'created_at': iso(m.created_at)}


def serialize_ticket(t, with_messages=False, staff=False):
    d = {'ticket_id': t.public_id, 'reference': t.reference, 'subject': t.subject, 'category': t.category,
         'priority': t.priority, 'status': t.status, 'created_at': iso(t.created_at), 'updated_at': iso(t.updated_at),
         'resolved_at': iso(t.resolved_at),
         'card': {'card_nickname': t.card.card_nickname, 'masked_number': f'•••• {t.card.last_four_digits}',
                  'issuer_name': t.card.issuer_name} if t.card else None,
         'payment': {'receipt_number': t.payment.receipt_number, 'amount': str(t.payment.amount),
                     'status': t.payment.status} if t.payment else None,
         'assignee': (t.assignee.full_name or 'Support agent') if t.assignee else None}
    if with_messages:
        msgs = t.messages if staff else t.messages.filter_by(is_internal=False)
        d['messages'] = [serialize_message(m, staff) for m in msgs]
    return d


def owned_ticket(ticket_id):
    return SupportTickets.query.filter_by(public_id=str(ticket_id)[:32], user_id=current_user().user_id).first()


@ns.route('')
class MyTickets(Resource):
    @ns.doc(description="The current user's support tickets.")
    @customer_required
    def get(self):
        q = SupportTickets.query.filter_by(user_id=current_user().user_id).order_by(SupportTickets.updated_at.desc())
        return ok(paged(q, serialize_ticket))

    @ns.doc(description='Raise a ticket. Optionally reference one of your own cards or payments.')
    @limiter.limit('10 per hour')
    @customer_required
    def post(self):
        try:
            user = current_user()
            body = _json()
            v = Validator()
            subject = clean_text(body.get('subject'))[:120]
            if len(subject) < 4:
                v.check('subject', 'Add a short subject (at least 4 characters).')
            category, e = validate_choice(body.get('category'), TicketCategory.CHOICES, 'Category', required=True)
            v.check('category', e)
            message, e = validate_body(body.get('message'))
            v.check('message', e)
            card = svc.owned_card(user.user_id, body['card_id']) if body.get('card_id') else None
            if body.get('card_id') and not card:
                v.check('card_id', 'Card not found.')
            payment = (PaymentTransactions.query.filter_by(public_id=str(body['payment_id'])[:32], user_id=user.user_id).first()
                       if body.get('payment_id') else None)
            if body.get('payment_id') and not payment:
                v.check('payment_id', 'Payment not found.')
            if not v.ok:
                return v.response()
            open_count = SupportTickets.query.filter(SupportTickets.user_id == user.user_id,
                                                     SupportTickets.status.in_(TicketStatus.ACTIVE)).count()
            if open_count >= MAX_OPEN_TICKETS:
                return fail('You have too many open tickets. Please continue in an existing one.', 429, code='TOO_MANY_TICKETS')

            t = SupportTickets(reference=new_reference(), user_id=user.user_id, subject=subject, category=category,
                               priority='HIGH' if category in ('PAYMENT', 'SECURITY') else 'NORMAL',
                               card_id=card.card_id if card else None, payment_id=payment.payment_id if payment else None)
            db.session.add(t)
            db.session.flush()
            db.session.add(SupportMessages(ticket_id=t.ticket_id, sender_id=user.user_id, sender_role=RoleName.USER, body=message))
            db.session.commit()
            audit('TICKET_CREATED', user.user_id, 'TICKET', t.reference, details={'category': category})
            return ok({'ticket': serialize_ticket(t, with_messages=True)}, 201)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'tickets/post')


@ns.route('/<string:ticket_id>')
class MyTicket(Resource):
    @customer_required
    def get(self, ticket_id):
        t = owned_ticket(ticket_id)
        return ok({'ticket': serialize_ticket(t, with_messages=True)}) if t else fail('Ticket not found.', 404, code='NOT_FOUND')


@ns.route('/<string:ticket_id>/messages')
class MyTicketReply(Resource):
    @limiter.limit('30 per hour')
    @customer_required
    def post(self, ticket_id):
        try:
            t = owned_ticket(ticket_id)
            if not t:
                return fail('Ticket not found.', 404, code='NOT_FOUND')
            if t.status == TicketStatus.CLOSED:
                return fail('This ticket is closed. Please raise a new one.', 409, code='TICKET_CLOSED')
            message, e = validate_body(_json().get('message'))
            if e:
                return fail(e, 400, code='VALIDATION_ERROR', errors={'message': e})
            db.session.add(SupportMessages(ticket_id=t.ticket_id, sender_id=current_user().user_id,
                                           sender_role=RoleName.USER, body=message))
            if t.status in (TicketStatus.WAITING_ON_USER, TicketStatus.RESOLVED):
                t.status = TicketStatus.OPEN if t.assigned_to is None else TicketStatus.IN_PROGRESS
                t.resolved_at = None
            t.updated_at = utcnow()
            db.session.commit()
            return ok({'ticket': serialize_ticket(t, with_messages=True)}, 201)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'tickets/reply')
