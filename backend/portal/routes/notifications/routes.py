"""In-app notifications. Bill-due reminders are generated on read (no scheduler
needed): for each card with dues inside BILL_DUE_REMINDER_DAYS, one reminder per
due date, de-duplicated by dedupe_key."""

from datetime import date, timedelta

from flask import request
from flask_restx import Resource

from portal import db
from portal.helpers.activity import notify
from portal.helpers.auth import auth_required, current_user
from portal.helpers.card_math import money
from portal.helpers.pagination import paged
from portal.helpers.responses import ok
from portal.helpers.settings import get_setting
from portal.models.base import iso, utcnow
from portal.models.linked_cards import LinkedCards
from portal.models.notifications import Notifications, NotificationType
from portal.models.roles import RoleName

from . import ns, logger


def _due_reminders(user):
    if user.role_name != RoleName.USER:
        return
    days = get_setting('BILL_DUE_REMINDER_DAYS', 3)
    today = date.today()
    cards = LinkedCards.query.filter(LinkedCards.user_id == user.user_id, LinkedCards.is_active.is_(True),
                                     LinkedCards.due_date.isnot(None), LinkedCards.outstanding_balance > 0,
                                     LinkedCards.due_date <= today + timedelta(days=days),
                                     LinkedCards.due_date >= today - timedelta(days=7)).all()
    for c in cards:
        overdue = c.due_date < today
        title = (f'{c.card_nickname} bill is overdue' if overdue else
                 f'{c.card_nickname} bill due {"today" if c.due_date == today else c.due_date.strftime("%d %b")}')
        notify(user.user_id, NotificationType.BILL_DUE, title,
               f'Outstanding {money(c.outstanding_balance)} INR on {c.issuer_name} ending {c.last_four_digits}.',
               link=f'/user/bills?card={c.public_id}',
               dedupe_key=f'due:{c.card_id}:{c.due_date.isoformat()}:{"over" if overdue else "soon"}')


def serialize(n):
    return {'notification_id': n.public_id, 'type': n.type, 'title': n.title, 'body': n.body, 'link': n.link,
            'is_read': n.is_read, 'created_at': iso(n.created_at)}


@ns.route('')
class List(Resource):
    @ns.doc(params={'unread': 'true = unread only', 'page': '', 'per_page': ''})
    @auth_required
    def get(self):
        user = current_user()
        try:
            _due_reminders(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception('[notifications] reminder generation failed')
        q = Notifications.query.filter_by(user_id=user.user_id)
        if request.args.get('unread') == 'true':
            q = q.filter_by(is_read=False)
        res = paged(q.order_by(Notifications.created_at.desc()), serialize, default=20, maximum=50)
        res['unread'] = Notifications.query.filter_by(user_id=user.user_id, is_read=False).count()
        return ok(res)


@ns.route('/unread-count')
class Unread(Resource):
    @auth_required
    def get(self):
        return ok({'unread': Notifications.query.filter_by(user_id=current_user().user_id, is_read=False).count()})


@ns.route('/read')
class MarkRead(Resource):
    @ns.doc(description='Mark notifications read: {"ids": [...]} or {"all": true}.')
    @auth_required
    def post(self):
        body = request.get_json(silent=True) or {}
        q = Notifications.query.filter_by(user_id=current_user().user_id, is_read=False)
        if body.get('all') is not True:
            ids = [str(i)[:32] for i in (body.get('ids') or [])][:100]
            q = q.filter(Notifications.public_id.in_(ids))
        n = q.update({'is_read': True, 'read_at': utcnow()}, synchronize_session=False)
        db.session.commit()
        return ok({'marked': n})
