"""
Credit cards: manual entry, listing, details, removal, provider linking,
refresh and consent management.

Every card lookup goes through card_service.owned_card(user_id, public_id), so a
card id belonging to another user is indistinguishable from a missing one (404).
"""

import secrets
from datetime import timedelta

from flask import current_app, redirect, request
from flask_restx import Resource
from sqlalchemy.exc import IntegrityError

from portal import db
from portal.extensions import limiter
from portal.helpers import card_service as svc
from portal.helpers import encryption
from portal.helpers.audit import audit
from portal.helpers.auth import customer_required, current_user, hash_token
from portal.helpers.card_math import money
from portal.helpers.responses import fail, ok, server_error
from portal.helpers.validators import (
    Validator, validate_amount, validate_bank_name, validate_choice, validate_date,
    validate_int_range, validate_last4, validate_nickname,
)
from portal.models.base import iso, utcnow
from portal.models.card_issuers import CardIssuers
from portal.models.card_link_sessions import CardLinkSessions, LinkSessionStatus
from portal.models.card_transactions import CardTransactions
from portal.models.financial_consents import FinancialConsents, ConsentStatus
from portal.models.linked_cards import LinkedCards, CardSource, VerificationStatus
from portal.models.card_networks import CardNetworks
from portal.models.payment_transactions import PaymentTransactions
from portal.providers.card_data.base import (
    ConsentExpired, ConsentRevoked, ProviderError, ProviderNotConfigured,
)
from portal.providers.card_data.registry import get_provider, validate_card_data

from . import ns, logger

MAX_CARDS_PER_USER = 20
FORBIDDEN_FIELDS = {'card_number', 'full_card_number', 'pan', 'cvv', 'cvc', 'expiry', 'expiry_date',
                    'pin', 'card_pin', 'otp', 'password', 'net_banking_password'}
FINANCIAL_FIELDS = {'credit_limit', 'outstanding_balance', 'available_credit', 'minimum_amount_due',
                    'billing_day', 'due_date'}
LINK_PURPOSE = 'Show your credit card limit, balance, dues and statement in CardVault'


def _json():
    return request.get_json(silent=True) or {}


def _not_found():
    return fail('Card not found.', 404, code='NOT_FOUND')


def _forbidden_fields(body):
    bad = sorted(FORBIDDEN_FIELDS & {k.lower() for k in body})
    if bad:
        return fail('For your security we never collect full card numbers, CVV, expiry, PINs, OTPs or '
                    'bank passwords. Only the last 4 digits are needed.', 400, code='SENSITIVE_DATA_REJECTED')
    return None


def _validate_financials(body, v, partial=False):
    """Returns dict of validated financial fields present in body. Cross-field
    rules are applied against `existing` values when updating."""
    out = {}
    if not partial or 'credit_limit' in body:
        out['credit_limit'], e = validate_amount(body.get('credit_limit'), 'Total credit limit',
                                                 required=True, allow_zero=False)
        v.check('credit_limit', e)
    for f, label in (('outstanding_balance', 'Outstanding balance'), ('available_credit', 'Available credit'),
                     ('minimum_amount_due', 'Minimum amount due')):
        if not partial or f in body:
            out[f], e = validate_amount(body.get(f), label)
            v.check(f, e)
    if not partial or 'billing_day' in body:
        out['billing_day'], e = validate_int_range(body.get('billing_day'), 'Billing cycle date', 1, 31)
        v.check('billing_day', e)
    if not partial or 'due_date' in body:
        out['due_date'], e = validate_date(body.get('due_date'), 'Payment due date')
        v.check('due_date', e)
    return out


def _cross_check(values, v):
    lim, out, avail, mind = (values.get(k) for k in
                             ('credit_limit', 'outstanding_balance', 'available_credit', 'minimum_amount_due'))
    if lim is not None and avail is not None and avail > lim:
        v.check('available_credit', 'Available credit cannot exceed the total credit limit.')
    if out is not None and mind is not None and mind > out:
        v.check('minimum_amount_due', 'Minimum amount due cannot exceed the outstanding balance.')
    if lim is not None and out is not None and out > lim * 2:
        v.check('outstanding_balance', 'Outstanding balance looks too high for this credit limit — please check.')


def _network_codes():
    return [c for (c,) in db.session.query(CardNetworks.code).filter_by(is_active=True)]


# ── Issuers & link configuration ────────────────────────────────────────────

@ns.route('/networks')
class Networks(Resource):
    @ns.doc(description='Card networks for the card-type dropdown.')
    @customer_required
    def get(self):
        rows = CardNetworks.query.filter_by(is_active=True).order_by(CardNetworks.sort_order).all()
        return ok({'networks': [n.to_dict() for n in rows]})


@ns.route('/issuers')
class Issuers(Resource):
    @ns.doc(description='Supported issuing banks, with whether each can be bank-linked right now.')
    @customer_required
    def get(self):
        provider = get_provider()
        linkable = set(provider.institution_ids().keys()) if provider else set()
        rows = CardIssuers.query.filter_by(is_active=True).order_by(CardIssuers.sort_order, CardIssuers.name).all()
        return ok({'issuers': [{**i.to_dict(), 'linkable': i.code in linkable} for i in rows]})


@ns.route('/link/config')
class LinkConfig(Resource):
    @ns.doc(description='Whether an authorised bank-data provider is configured, and what it can supply.')
    @customer_required
    def get(self):
        provider = get_provider()
        if not provider:
            return ok({'configured': False, 'message': 'Bank integration not configured. '
                       'You can add your card manually — it will be labelled "User-entered — Not Bank Verified".'})
        caps = provider.capabilities()
        return ok({'configured': True, 'provider': provider.display_name, 'capabilities': caps,
                   'supported_issuer_codes': sorted(provider.institution_ids().keys()),
                   'purpose': LINK_PURPOSE,
                   'data_accessed': [k.replace('_', ' ') for k, v in caps.items() if v and k != 'refresh']})


# ── Cards collection ────────────────────────────────────────────────────────

@ns.route('')
class Cards(Resource):
    @ns.doc(description="List the current user's active cards with a portfolio summary.")
    @customer_required
    def get(self):
        user = current_user()
        cards = (LinkedCards.query.filter_by(user_id=user.user_id, is_active=True)
                 .order_by(LinkedCards.created_at.asc()).all())
        return ok({'cards': [svc.serialize_card(c) for c in cards], 'summary': svc.portfolio_summary(cards)})

    @ns.doc(description='Add a card manually. Values are stored as "User-entered — Not Bank Verified".')
    @limiter.limit('20 per minute')
    @customer_required
    def post(self):
        try:
            user = current_user()
            body = _json()
            blocked = _forbidden_fields(body)
            if blocked:
                return blocked

            v = Validator()
            issuer_id, e = validate_int_range(body.get('issuer_id'), 'Issuing bank', 1, 10 ** 9, required=True)
            v.check('issuer_id', e)
            issuer = CardIssuers.query.filter_by(issuer_id=issuer_id, is_active=True).first() if issuer_id else None
            if issuer_id and not issuer:
                v.check('issuer_id', 'Select a supported bank.')
            issuer_name = issuer.name if issuer else None
            if issuer and issuer.code == 'OTHER':
                issuer_name, e = validate_bank_name(body.get('issuer_name'))
                v.check('issuer_name', e)
            nickname, e = validate_nickname(body.get('card_nickname'))
            v.check('card_nickname', e)
            last4, e = validate_last4(body.get('last_four_digits'))
            v.check('last_four_digits', e)
            network, e = validate_choice(body.get('card_network'), _network_codes(), 'Card type')
            v.check('card_network', e)
            fin = _validate_financials(body, v)
            _cross_check(fin, v)
            if not v.ok:
                return v.response()

            if LinkedCards.query.filter_by(user_id=user.user_id, is_active=True).count() >= MAX_CARDS_PER_USER:
                return fail(f'You can add up to {MAX_CARDS_PER_USER} cards.', 400, code='CARD_LIMIT')

            key = LinkedCards.build_dedupe_key(user.user_id, issuer_name, last4)
            if LinkedCards.query.filter_by(dedupe_key=key).first():
                return fail(f'You have already added the {issuer_name} card ending {last4}.', 409, code='DUPLICATE_CARD')

            card = LinkedCards(
                user_id=user.user_id, issuer_id=issuer.issuer_id, issuer_name=issuer_name,
                card_nickname=nickname, card_network=network, last_four_digits=last4,
                card_source=CardSource.USER_ENTERED, verification_status=VerificationStatus.UNVERIFIED,
                currency='INR', data_as_of=utcnow(), dedupe_key=key, **fin)
            db.session.add(card)
            db.session.flush()
            svc.record_snapshot(card, CardSource.USER_ENTERED, note='manual entry')
            svc.upsert_current_bill(card)
            db.session.commit()
            audit('CARD_ADDED_MANUAL', user.user_id, 'CARD', card.public_id, details={'issuer': issuer.code})
            return ok({'message': 'Card added. Figures are user-entered and not bank verified.',
                       'card': svc.serialize_card(card)}, 201)
        except IntegrityError:
            db.session.rollback()
            return fail('This card has already been added.', 409, code='DUPLICATE_CARD')
        except Exception:
            db.session.rollback()
            return server_error(logger, 'cards/post')


# ── Single card ─────────────────────────────────────────────────────────────

@ns.route('/<string:card_id>')
class Card(Resource):
    @ns.doc(description='Card details (owner only).')
    @customer_required
    def get(self, card_id):
        card = svc.owned_card(current_user().user_id, card_id)
        return ok({'card': svc.serialize_card(card, detail=True)}) if card else _not_found()

    @ns.doc(description='Edit a card. Financial fields are editable only on user-entered cards — '
                        'provider-verified figures are read-only.')
    @limiter.limit('30 per minute')
    @customer_required
    def patch(self, card_id):
        try:
            user = current_user()
            card = svc.owned_card(user.user_id, card_id)
            if not card:
                return _not_found()
            body = _json()
            blocked = _forbidden_fields(body)
            if blocked:
                return blocked
            touches_fin = bool(FINANCIAL_FIELDS & set(body))
            if touches_fin and card.card_source != CardSource.USER_ENTERED:
                return fail('Bank-verified figures cannot be edited. Use Refresh to update them.', 403,
                            code='PROVIDER_DATA_READ_ONLY')
            v = Validator()
            if 'card_nickname' in body:
                nickname, e = validate_nickname(body.get('card_nickname'))
                v.check('card_nickname', e)
            fin = _validate_financials(body, v, partial=True) if touches_fin else {}
            merged = {k: fin.get(k, getattr(card, k)) for k in
                      ('credit_limit', 'outstanding_balance', 'available_credit', 'minimum_amount_due')}
            _cross_check(merged, v)
            if not v.ok:
                return v.response()

            if 'card_nickname' in body:
                card.card_nickname = nickname
            if fin:
                for k, val in fin.items():
                    setattr(card, k, val)
                card.data_as_of = utcnow()
                db.session.flush()
                svc.record_snapshot(card, CardSource.USER_ENTERED, note='manual update')
                svc.upsert_current_bill(card)
            db.session.commit()
            audit('CARD_UPDATED', user.user_id, 'CARD', card.public_id, details={'fields': sorted(body)})
            return ok({'message': 'Card updated.', 'card': svc.serialize_card(card, detail=True)})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'cards/patch')

    @ns.doc(description='Remove a card. Deletes its stored figures, snapshots and transactions and '
                        'revokes provider consent if no other card uses it. Payment records are kept '
                        'for reconciliation.')
    @customer_required
    def delete(self, card_id):
        try:
            user = current_user()
            card = svc.owned_card(user.user_id, card_id)
            if not card:
                return _not_found()

            consent = card.consent
            card.is_active = False
            card.removed_at = utcnow()
            card.dedupe_key = None
            for f in ('credit_limit', 'outstanding_balance', 'available_credit', 'minimum_amount_due'):
                setattr(card, f, None)
            card.snapshots.delete(synchronize_session=False)
            CardTransactions.query.filter_by(card_id=card.card_id).delete(synchronize_session=False)
            db.session.flush()

            if consent and consent.status == ConsentStatus.ACTIVE:
                still_used = LinkedCards.query.filter_by(consent_id=consent.consent_id, is_active=True).count()
                if not still_used:
                    _revoke_consent(consent)
            db.session.commit()
            audit('CARD_REMOVED', user.user_id, 'CARD', card.public_id)
            return ok({'message': 'Card removed.'})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'cards/delete')


@ns.route('/<string:card_id>/summary')
class CardSummary(Resource):
    @ns.doc(description='Financial summary with provenance: which values are reported vs estimated, '
                        'their source and as-of time, plus recent snapshots.')
    @customer_required
    def get(self, card_id):
        card = svc.owned_card(current_user().user_id, card_id)
        if not card:
            return _not_found()
        snaps = card.snapshots.order_by(db.desc('captured_at')).limit(10).all()
        return ok({
            'card_id': card.public_id,
            'source': card.card_source,
            'source_label': svc.SOURCE_LABELS.get(card.card_source),
            'verification_status': card.verification_status,
            **svc.financials(card),
            'history': [{'captured_at': iso(s.captured_at), 'data_as_of': iso(s.data_as_of), 'source': s.source,
                         'credit_limit': money(s.credit_limit), 'outstanding_balance': money(s.outstanding_balance),
                         'note': s.note} for s in snaps],
        })


@ns.route('/<string:card_id>/transactions')
class CardTxns(Resource):
    @ns.doc(description='Statement transactions — only for bank-linked cards whose provider supplies them.',
            params={'page': 'Page (default 1)', 'per_page': 'Items per page (max 50)'})
    @customer_required
    def get(self, card_id):
        card = svc.owned_card(current_user().user_id, card_id)
        if not card:
            return _not_found()
        if card.card_source != CardSource.PROVIDER:
            return ok({'available': False, 'transactions': [], 'message':
                       'Transaction history is only available for bank-linked cards.'})
        page = max(request.args.get('page', 1, type=int), 1)
        per_page = min(max(request.args.get('per_page', 20, type=int), 1), 50)
        q = CardTransactions.query.filter_by(card_id=card.card_id).order_by(CardTransactions.txn_date.desc())
        p = q.paginate(page=page, per_page=per_page, error_out=False)
        return ok({'available': True, 'page': page, 'pages': p.pages, 'total': p.total, 'transactions': [
            {'date': t.txn_date.isoformat(), 'description': t.description, 'amount': money(t.amount),
             'type': t.txn_type, 'status': t.txn_status} for t in p.items]})


@ns.route('/<string:card_id>/payments')
class CardPayments(Resource):
    @ns.doc(description='Payments made for this card through the app.')
    @customer_required
    def get(self, card_id):
        user = current_user()
        card = svc.owned_card(user.user_id, card_id)
        if not card:
            return _not_found()
        from portal.routes.bills.routes import serialize_payment
        rows = (PaymentTransactions.query.filter_by(user_id=user.user_id, card_id=card.card_id)
                .order_by(PaymentTransactions.created_at.desc()).limit(50).all())
        return ok({'payments': [serialize_payment(p) for p in rows]})


@ns.route('/<string:card_id>/refresh')
class CardRefresh(Resource):
    @ns.doc(description='Re-fetch figures from the authorised provider (bank-linked cards only).')
    @limiter.limit('10 per hour')
    @customer_required
    def post(self, card_id):
        try:
            user = current_user()
            card = svc.owned_card(user.user_id, card_id)
            if not card:
                return _not_found()
            if card.card_source != CardSource.PROVIDER or not card.consent:
                return fail('Refresh is only available for bank-linked cards. Edit manual cards instead.',
                            400, code='REFRESH_NOT_SUPPORTED')
            consent = card.consent
            if consent.status != ConsentStatus.ACTIVE:
                return fail('Data-sharing consent is no longer active. Re-link this card.', 409,
                            code=f'CONSENT_{consent.status}')
            if consent.consent_expires_at and consent.consent_expires_at < utcnow():
                _mark_consent(consent, ConsentStatus.EXPIRED)
                db.session.commit()
                return fail(ConsentExpired.user_message, 409, code=ConsentExpired.code)
            provider = get_provider()
            if not provider or provider.name != card.provider_name:
                return fail(ProviderNotConfigured.user_message, 503, code=ProviderNotConfigured.code)

            try:
                data = provider.refresh_card_data(access_token=encryption.decrypt(consent.encrypted_access_token),
                                                  provider_reference=card.provider_reference)
                data = validate_card_data(data)
            except (ConsentExpired, ConsentRevoked) as e:
                _mark_consent(consent, ConsentStatus.EXPIRED if isinstance(e, ConsentExpired) else ConsentStatus.REVOKED)
                db.session.commit()
                audit('CARD_REFRESH', user.user_id, 'CARD', card.public_id, status='FAILED', details={'code': e.code})
                return fail(e.user_message, e.http_status, code=e.code)
            except ProviderError as e:
                db.session.rollback()
                logger.warning(f'[cards/refresh] provider error {e.code}: {e}')
                audit('CARD_REFRESH', user.user_id, 'CARD', card.public_id, status='FAILED', details={'code': e.code})
                return fail(e.user_message + ' Showing the last verified figures.', e.http_status, code=e.code)

            if data.last_four_digits != card.last_four_digits:
                logger.error('[cards/refresh] provider returned a different card for this reference')
                return fail('The bank returned data for a different card, so nothing was changed.', 502,
                            code='INVALID_PROVIDER_RESPONSE')
            svc.apply_provider_data(card, data, provider)
            db.session.commit()
            audit('CARD_REFRESH', user.user_id, 'CARD', card.public_id)
            return ok({'message': 'Card data refreshed from your bank.', 'card': svc.serialize_card(card, detail=True)})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'cards/refresh')


# ── Provider linking ────────────────────────────────────────────────────────

def _mark_consent(consent, status):
    consent.status = status
    if status in (ConsentStatus.REVOKED, ConsentStatus.EXPIRED):
        consent.encrypted_access_token = None
        consent.revoked_at = utcnow() if status == ConsentStatus.REVOKED else consent.revoked_at
        vs = VerificationStatus.CONSENT_REVOKED if status == ConsentStatus.REVOKED else VerificationStatus.CONSENT_EXPIRED
        LinkedCards.query.filter_by(consent_id=consent.consent_id, is_active=True) \
            .update({'verification_status': vs}, synchronize_session=False)


def _revoke_consent(consent):
    provider = get_provider()
    if provider and provider.name == consent.provider_name and consent.encrypted_access_token:
        try:
            provider.revoke_link(access_token=encryption.decrypt(consent.encrypted_access_token),
                                 consent_reference=consent.consent_reference)
        except Exception as e:      # still revoke locally; provider-side revoke can be retried
            logger.warning(f'[consent] provider revoke failed: {e.__class__.__name__}')
    _mark_consent(consent, ConsentStatus.REVOKED)


@ns.route('/link-session')
class LinkSession(Resource):
    @ns.doc(description='Start an authorised bank-linking flow. Returns the provider-hosted consent URL. '
                        'This app never shows a bank login page or asks for bank credentials/OTPs.')
    @limiter.limit('10 per hour')
    @customer_required
    def post(self):
        try:
            user = current_user()
            body = _json()
            provider = get_provider()
            if not provider:
                return fail(ProviderNotConfigured.user_message, 503, code=ProviderNotConfigured.code)
            if body.get('consent_acknowledged') is not True:
                return fail('Please review and accept what data will be shared.', 400, code='CONSENT_REQUIRED')
            issuer_id, e = validate_int_range(body.get('issuer_id'), 'Issuing bank', 1, 10 ** 9, required=True)
            issuer = CardIssuers.query.filter_by(issuer_id=issuer_id, is_active=True).first() if not e else None
            if not issuer:
                return fail('Select a supported bank.', 400, code='VALIDATION_ERROR')
            institution = provider.institution_ids().get(issuer.code)
            if not institution:
                return fail(f'{issuer.name} cannot be linked through {provider.display_name} yet. '
                            'Add the card manually instead.', 422, code='ISSUER_NOT_SUPPORTED')

            state = secrets.token_urlsafe(32)
            caps = provider.capabilities()
            consent = FinancialConsents(user_id=user.user_id, provider_name=provider.name, purpose=LINK_PURPOSE,
                                        data_scope=[k for k, v in caps.items() if v], status=ConsentStatus.PENDING)
            db.session.add(consent)
            db.session.flush()
            ls = CardLinkSessions(
                user_id=user.user_id, issuer_id=issuer.issuer_id, provider_name=provider.name,
                state_hash=hash_token(state), consent_id=consent.consent_id,
                expires_at=utcnow() + timedelta(minutes=current_app.config['LINK_SESSION_TTL_MINUTES']))
            db.session.add(ls)
            db.session.flush()

            try:
                result = provider.create_link_session(
                    user_ref=user.public_id, institution_id=institution, state=state, purpose=LINK_PURPOSE,
                    redirect_uri=f"{current_app.config['BACKEND_PUBLIC_URL']}/v1/cards/link/callback")
            except ProviderError as pe:
                db.session.rollback()
                return fail(pe.user_message, pe.http_status, code=pe.code)

            ls.provider_session_ref = result.provider_session_ref
            ls.status = LinkSessionStatus.AWAITING_USER
            db.session.commit()
            audit('CARD_LINK_STARTED', user.user_id, 'LINK_SESSION', ls.public_id, details={'issuer': issuer.code})
            return ok({'session_id': ls.public_id, 'redirect_url': result.redirect_url,
                       'expires_at': iso(ls.expires_at)}, 201)
        except Exception:
            db.session.rollback()
            return server_error(logger, 'cards/link-session')


@ns.route('/link-status/<string:session_id>')
class LinkStatus(Resource):
    @ns.doc(description='Status of a linking session (owner only).')
    @customer_required
    def get(self, session_id):
        ls = CardLinkSessions.query.filter_by(public_id=session_id[:32], user_id=current_user().user_id).first()
        if not ls:
            return fail('Link session not found.', 404, code='NOT_FOUND')
        if ls.status not in LinkSessionStatus.TERMINAL and ls.expires_at < utcnow():
            ls.status = LinkSessionStatus.EXPIRED
            db.session.commit()
        return ok({'session_id': ls.public_id, 'status': ls.status, 'cards_linked': ls.cards_linked,
                   'error_code': ls.error_code, 'error_message': ls.error_message,
                   'completed_at': iso(ls.completed_at)})


def _fail_link(ls, code, message):
    ls.status = LinkSessionStatus.FAILED
    ls.error_code, ls.error_message = code, message[:255]
    if ls.consent_id:
        c = db.session.get(FinancialConsents, ls.consent_id)
        if c and c.status == ConsentStatus.PENDING:
            c.status = ConsentStatus.REJECTED
    db.session.commit()


@ns.route('/link/callback')
class LinkCallback(Resource):
    @ns.doc(description='Provider redirect target. Bound to the user by the single-use `state`; '
                        'always redirects back to the app.')
    @limiter.limit('30 per minute')
    def get(self):
        front = current_app.config['FRONTEND_URL'] + '/user/cards'
        state = request.args.get('state', '')
        ls = CardLinkSessions.query.filter_by(state_hash=hash_token(state)).first() if state else None
        if not ls:
            return redirect(f'{front}?link_error=invalid_state')
        if ls.status != LinkSessionStatus.AWAITING_USER:
            return redirect(f'{front}?link_session={ls.public_id}')
        if ls.expires_at < utcnow():
            ls.status = LinkSessionStatus.EXPIRED
            db.session.commit()
            return redirect(f'{front}?link_session={ls.public_id}')
        try:
            _complete_link(ls, dict(request.args))
        except ProviderError as e:
            db.session.rollback()
            _fail_link(ls, e.code, e.user_message)
        except Exception:
            db.session.rollback()
            logger.exception('[cards/link/callback] failed')
            _fail_link(ls, 'SERVER_ERROR', 'Linking failed. Please try again.')
        return redirect(f'{front}?link_session={ls.public_id}')


def _complete_link(ls, params):
    provider = get_provider()
    if not provider or provider.name != ls.provider_name:
        raise ProviderNotConfigured()
    result = provider.exchange_callback(params=params)
    if result.status != 'ACTIVE' or not result.access_token:
        _fail_link(ls, 'CONSENT_NOT_GRANTED', 'Consent was not granted at the provider.')
        return

    consent = db.session.get(FinancialConsents, ls.consent_id)
    consent.status = ConsentStatus.ACTIVE
    consent.consent_reference = result.consent_reference
    consent.encrypted_access_token = encryption.encrypt(result.access_token)
    consent.token_expires_at = result.token_expires_at
    consent.consent_expires_at = result.consent_expires_at
    if result.data_scope:
        consent.data_scope = result.data_scope

    items = [validate_card_data(i) for i in provider.fetch_supported_card_data(access_token=result.access_token)]
    issuer = db.session.get(CardIssuers, ls.issuer_id)
    linked = 0
    for data in items:
        card = (LinkedCards.query.filter_by(user_id=ls.user_id, provider_name=provider.name,
                                            provider_reference=data.provider_reference, is_active=True).first())
        if card is None:
            key = LinkedCards.build_dedupe_key(ls.user_id, issuer.name, data.last_four_digits)
            # Upgrade a manual card for the same bank + last 4 to verified, or create a new one.
            card = LinkedCards.query.filter_by(dedupe_key=key).first()
            if card is None:
                card = LinkedCards(user_id=ls.user_id, issuer_id=issuer.issuer_id, issuer_name=issuer.name,
                                   card_nickname=f'{issuer.short_name} ••{data.last_four_digits}',
                                   last_four_digits=data.last_four_digits, dedupe_key=key)
                db.session.add(card)
        card.consent_id = consent.consent_id
        svc.apply_provider_data(card, data, provider)
        linked += 1

    if linked == 0:
        _fail_link(ls, 'DATA_UNAVAILABLE', 'Your bank did not share any credit card data.')
        return
    ls.status = LinkSessionStatus.COMPLETED
    ls.cards_linked = linked
    ls.completed_at = utcnow()
    db.session.commit()
    audit('CARD_LINK_COMPLETED', ls.user_id, 'LINK_SESSION', ls.public_id, details={'cards': linked})


@ns.route('/link/webhook')
class LinkWebhook(Resource):
    @ns.doc(description='Provider consent-status webhook. Rejected unless its signature verifies.')
    @limiter.limit('120 per minute')
    def post(self):
        provider = get_provider()
        raw = request.get_data(cache=False)
        if not provider or not provider.verify_webhook(headers=dict(request.headers), raw_body=raw):
            return fail('Invalid signature.', 401, code='INVALID_SIGNATURE')
        try:
            for ev in provider.parse_webhook(raw_body=raw):
                consent = FinancialConsents.query.filter_by(provider_name=provider.name,
                                                            consent_reference=ev.get('consent_reference')).first()
                if consent and ev.get('status') in (ConsentStatus.REVOKED, ConsentStatus.EXPIRED, ConsentStatus.REJECTED):
                    _mark_consent(consent, ev['status'])
            db.session.commit()
            return ok({'received': True})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'cards/link/webhook')


# ── Consents (privacy controls) ─────────────────────────────────────────────

@ns.route('/consents')
class Consents(Resource):
    @ns.doc(description="The user's data-sharing consents.")
    @customer_required
    def get(self):
        rows = (FinancialConsents.query.filter_by(user_id=current_user().user_id)
                .filter(FinancialConsents.status != ConsentStatus.PENDING)
                .order_by(FinancialConsents.created_at.desc()).all())
        return ok({'consents': [{
            'consent_id': c.public_id, 'provider_name': c.provider_name, 'purpose': c.purpose,
            'data_scope': c.data_scope, 'status': c.status, 'created_at': iso(c.created_at),
            'consent_expires_at': iso(c.consent_expires_at), 'revoked_at': iso(c.revoked_at),
            'cards': [x.card_nickname for x in LinkedCards.query.filter_by(consent_id=c.consent_id, is_active=True)],
        } for c in rows]})


@ns.route('/consents/<string:consent_id>/revoke')
class ConsentRevoke(Resource):
    @ns.doc(description='Revoke a data-sharing consent. Linked cards keep their last verified figures '
                        '(marked as no longer refreshable) until removed.')
    @customer_required
    def post(self, consent_id):
        try:
            user = current_user()
            c = FinancialConsents.query.filter_by(public_id=consent_id[:32], user_id=user.user_id).first()
            if not c:
                return fail('Consent not found.', 404, code='NOT_FOUND')
            if c.status != ConsentStatus.ACTIVE:
                return fail('This consent is not active.', 409, code='CONSENT_NOT_ACTIVE')
            _revoke_consent(c)
            db.session.commit()
            audit('CONSENT_REVOKED', user.user_id, 'CONSENT', c.public_id)
            return ok({'message': 'Consent revoked.'})
        except Exception:
            db.session.rollback()
            return server_error(logger, 'consents/revoke')
