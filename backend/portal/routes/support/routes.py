"""Customer Support API (SUPPORT and ADMIN roles).

Agents see the ticket queue, reply to customers, add internal notes, change
status/assignment, and look up a customer's context. Customer data is
READ-ONLY and MASKED here: last 4 card digits, masked mobile, no tokens,
no consent secrets, and nothing that would let an agent act as the user.
"""

from flask import request
from flask_restx import Resource
from sqlalchemy import or_

from portal import db
from portal.helpers import card_service as svc
from portal.helpers.audit import audit
from portal.helpers.auth import current_user, role_required
from portal.helpers.pagination import paged
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.validators import clean_text, normalize_mobile, validate_choice
from portal.models.base import iso, utcnow
from portal.models.linked_cards import LinkedCards
from portal.models.payment_transactions import PaymentTransactions
from portal.models.roles import Roles, RoleName
from portal.models.support_messages import SupportMessages
from portal.models.support_tickets import SupportTickets, TicketPriority, TicketStatus
from portal.models.users import Users
from portal.routes.bills.routes import serialize_payment
from portal.routes.tickets.routes import serialize_ticket, validate_body
from portal.helpers.activity import notify
from portal.models.notifications import NotificationType

from . import ns, logger

staff_only = role_required(RoleName.SUPPORT, RoleName.ADMIN)


def _json():
    return request.get_json(silent=True) or {}


def _customer(u):
    return {'user_id': u.public_id, 'full_name': u.full_name, 'mobile_number': u.masked_mobile,
            'status': u.status, 'member_since': iso(u.created_on), 'last_login': iso(u.last_login)}


def _customer_context(u):
    """Masked, read-only snapshot an agent needs to help — no secrets, no full numbers."""
    cards = LinkedCards.query.filter_by(user_id=u.user_id, is_active=True).all()
    pays = (PaymentTransactions.query.filter_by(user_id=u.user_id)
            .order_by(PaymentTransactions.created_at.desc()).limit(10).all())
    return {
        'customer': _customer(u),
        'cards': [{'card_nickname': c.card_nickname, 'issuer_name': c.issuer_name,
                   'masked_number': f'•••• {c.last_four_digits}', 'source': c.card_source,
                   'verification_status': c.verification_status, 'due_date': c.due_date.isoformat() if c.due_date else None,
                   'bill_status': svc.financials(c)['bill_status'], 'data_as_of': iso(c.data_as_of)} for c in cards],
        'recent_payments': [serialize_payment(p) for p in pays],
    }


def _staff_ticket(ticket_id):
    return SupportTickets.query.filter_by(public_id=str(ticket_id)[:32]).first()


@ns.route('/tickets')
class Queue(Resource):
    @ns.doc(description='Ticket queue.', params={'status': 'OPEN|IN_PROGRESS|WAITING_ON_USER|RESOLVED|CLOSED|ACTIVE',
                                                 'mine': 'true = assigned to me', 'q': 'reference or subject'})
    @staff_only
    def get(self):
        q = SupportTickets.query
        st = request.args.get('status', 'ACTIVE')
        if st == 'ACTIVE':
            q = q.filter(SupportTickets.status.in_(TicketStatus.ACTIVE))
        elif st in TicketStatus.CHOICES:
            q = q.filter_by(status=st)
        if request.args.get('mine') == 'true':
            q = q.filter_by(assigned_to=current_user().user_id)
        term = clean_text(request.args.get('q'))[:60]
        if term:
            like = '%' + term.replace('%', r'\%').replace('_', r'\_') + '%'
            q = q.filter(or_(SupportTickets.reference == term.upper(), SupportTickets.subject.ilike(like)))
        order = {'URGENT': 0, 'HIGH': 1, 'NORMAL': 2, 'LOW': 3}

        def ser(t):
            d = serialize_ticket(t, staff=True)
            d['customer'] = _customer(t.user)
            last = t.messages.order_by(SupportMessages.created_at.desc()).first()
            d['last_message'] = last.body[:120] if last else None
            return d
        res = paged(q.order_by(SupportTickets.updated_at.desc()), ser)
        res['items'].sort(key=lambda x: (x['status'] not in TicketStatus.ACTIVE, order.get(x['priority'], 9)))
        counts = {s: SupportTickets.query.filter_by(status=s).count() for s in TicketStatus.CHOICES}
        res['counts'] = counts
        return ok(res)


@ns.route('/tickets/<string:ticket_id>')
class Ticket(Resource):
    @staff_only
    def get(self, ticket_id):
        t = _staff_ticket(ticket_id)
        if not t:
            return fail('Ticket not found.', 404, code='NOT_FOUND')
        audit('SUPPORT_TICKET_VIEWED', current_user().user_id, 'TICKET', t.reference, commit=True)
        return ok({'ticket': serialize_ticket(t, with_messages=True, staff=True), **_customer_context(t.user)})

    @ns.doc(description='Update status / priority / assignment (assign_to_me: true, or unassign: true).')
    @staff_only
    def patch(self, ticket_id):
        try:
            t = _staff_ticket(ticket_id)
            if not t:
                return fail('Ticket not found.', 404, code='NOT_FOUND')
            body = _json()
            status, e1 = validate_choice(body.get('status'), TicketStatus.CHOICES, 'Status')
            priority, e2 = validate_choice(body.get('priority'), TicketPriority.CHOICES, 'Priority')
            if e1 or e2:
                return fail(e1 or e2, 400, code='VALIDATION_ERROR')
            before = {'status': t.status, 'priority': t.priority, 'assigned_to': t.assigned_to}
            if status:
                t.status = status
                t.resolved_at = utcnow() if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED) else None
            if priority:
                t.priority = priority
            if body.get('assign_to_me') is True:
                t.assigned_to = current_user().user_id
                if t.status == TicketStatus.OPEN:
                    t.status = TicketStatus.IN_PROGRESS
            elif body.get('unassign') is True:
                t.assigned_to = None
            t.updated_at = utcnow()
            db.session.commit()
            audit('SUPPORT_TICKET_UPDATED', current_user().user_id, 'TICKET', t.reference,
                  details={'before': before, 'after': {'status': t.status, 'priority': t.priority, 'assigned_to': t.assigned_to}})
            return ok({'ticket': serialize_ticket(t, with_messages=True, staff=True)})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'support/ticket/patch')


@ns.route('/tickets/<string:ticket_id>/messages')
class TicketReply(Resource):
    @ns.doc(description='Reply to the customer, or add an internal note (internal: true) visible to staff only.')
    @staff_only
    def post(self, ticket_id):
        try:
            t = _staff_ticket(ticket_id)
            if not t:
                return fail('Ticket not found.', 404, code='NOT_FOUND')
            body = _json()
            message, e = validate_body(body.get('message'))
            if e:
                return fail(e, 400, code='VALIDATION_ERROR', errors={'message': e})
            internal = body.get('internal') is True
            me = current_user()
            db.session.add(SupportMessages(ticket_id=t.ticket_id, sender_id=me.user_id, sender_role=me.role_name,
                                           body=message, is_internal=internal))
            if not internal:
                notify(t.user_id, NotificationType.SUPPORT, f'Support replied on {t.reference}',
                       message[:140], link='/user/help')
                if t.assigned_to is None:
                    t.assigned_to = me.user_id
                if t.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS):
                    t.status = TicketStatus.WAITING_ON_USER
            t.updated_at = utcnow()
            db.session.commit()
            audit('SUPPORT_REPLY' if not internal else 'SUPPORT_NOTE', me.user_id, 'TICKET', t.reference)
            return ok({'ticket': serialize_ticket(t, with_messages=True, staff=True)}, 201)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'support/reply')


@ns.route('/lookup')
class Lookup(Resource):
    @ns.doc(description='Find a customer by mobile number, or a payment by receipt / order / payment id. '
                        'Read-only, masked. Every lookup is audit-logged.',
            params={'mobile': '10-digit mobile', 'reference': 'receipt / order / payment id'})
    @staff_only
    def get(self):
        me = current_user()
        if request.args.get('mobile'):
            mobile, err = normalize_mobile(request.args['mobile'])
            if err:
                return fail(err, 400, code='VALIDATION_ERROR')
            u = Users.query.join(Roles).filter(Users.mobile_number == mobile, Roles.role_name == RoleName.USER).first()
            audit('SUPPORT_LOOKUP', me.user_id, 'USER', u.public_id if u else None, details={'by': 'mobile', 'found': bool(u)})
            if not u:
                return fail('No customer with that mobile number.', 404, code='NOT_FOUND')
            tickets = SupportTickets.query.filter_by(user_id=u.user_id).order_by(SupportTickets.created_at.desc()).limit(10)
            return ok({**_customer_context(u), 'tickets': [serialize_ticket(t, staff=True) for t in tickets]})
        ref = clean_text(request.args.get('reference'))[:64]
        if ref:
            p = PaymentTransactions.query.filter(or_(PaymentTransactions.receipt_number == ref,
                                                     PaymentTransactions.provider_order_id == ref,
                                                     PaymentTransactions.provider_payment_id == ref)).first()
            audit('SUPPORT_LOOKUP', me.user_id, 'PAYMENT', p.public_id if p else None, details={'by': 'reference', 'found': bool(p)})
            if not p:
                return fail('No payment with that reference.', 404, code='NOT_FOUND')
            return ok({'payment': serialize_payment(p), 'customer': _customer(db.session.get(Users, p.user_id))})
        return fail('Enter a mobile number or a payment reference.', 400, code='VALIDATION_ERROR')
