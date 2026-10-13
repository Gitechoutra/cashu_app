"""Card domain logic shared by the cards and bills routes."""

from decimal import Decimal

from flask import current_app
from sqlalchemy import func

from portal import db
from portal.models.base import iso, utcnow
from portal.models.bills import Bills
from portal.models.card_data_snapshots import CardDataSnapshots
from portal.models.card_transactions import CardTransactions
from portal.models.linked_cards import LinkedCards, CardSource, VerificationStatus
from portal.models.payment_transactions import PaymentTransactions, PaymentStatus
from . import card_math as cm

SOURCE_LABELS = {
    CardSource.USER_ENTERED: 'User-entered — Not Bank Verified',
    CardSource.PROVIDER: 'Provider-verified',
    CardSource.SAMPLE: 'Sample data — development only',
}


def owned_card(user_id, public_id, include_removed=False):
    """The ONLY way routes load a card: always scoped to the current user, so a
    guessed or tampered id from another account resolves to 404, never 403."""
    q = LinkedCards.query.filter_by(public_id=str(public_id)[:32], user_id=user_id)
    if not include_removed:
        q = q.filter_by(is_active=True)
    return q.first()


def current_bill(card):
    return (Bills.query.filter_by(card_id=card.card_id, is_current=True)
            .order_by(Bills.created_at.desc()).first())


def paid_in_app_since(card, since=None):
    """Sum of SUCCESS (server-verified) payments for this card since the statement date."""
    q = db.session.query(func.coalesce(func.sum(PaymentTransactions.amount), 0)).filter(
        PaymentTransactions.card_id == card.card_id,
        PaymentTransactions.status == PaymentStatus.SUCCESS)
    if since is not None:
        q = q.filter(PaymentTransactions.created_at >= since)
    return Decimal(str(q.scalar() or 0))


def financials(card):
    avail, basis, over = cm.available_credit(card.credit_limit, card.outstanding_balance, card.available_credit)
    util = cm.utilization_pct(card.outstanding_balance, card.credit_limit)
    paid = paid_in_app_since(card, card.statement_date)
    stale_hours = current_app.config['CARD_DATA_STALE_HOURS']
    is_provider = card.card_source == CardSource.PROVIDER
    return {
        'credit_limit': cm.money(card.credit_limit),
        'outstanding_balance': cm.money(card.outstanding_balance),
        'available_credit': cm.money(avail),
        'available_credit_basis': basis,          # REPORTED | ESTIMATED | UNKNOWN
        'over_limit': over,
        'minimum_amount_due': cm.money(card.minimum_amount_due),
        'utilization_pct': cm.money(util),
        'utilization_band': cm.utilization_band(util),
        'currency': card.currency,
        'billing_day': card.billing_day,
        'statement_date': card.statement_date.isoformat() if card.statement_date else None,
        'due_date': card.due_date.isoformat() if card.due_date else None,
        'bill_status': cm.bill_status(card.outstanding_balance, card.due_date, paid_in_app=paid),
        'paid_in_app_this_cycle': cm.money(paid),
        'data_as_of': iso(card.data_as_of),
        # Manual figures are "as entered", not "stale"; provider data ages out.
        'is_stale': is_provider and cm.is_stale(card.data_as_of, stale_hours),
    }


def serialize_card(card, detail=False):
    issuer = card.issuer
    data = {
        'card_id': card.public_id,
        'issuer_name': card.issuer_name,
        'issuer_code': issuer.code if issuer else None,
        'gradient': [issuer.gradient_from, issuer.gradient_to] if issuer else ['#1E293B', '#0F172A'],
        'card_nickname': card.card_nickname,
        'card_network': card.card_network,
        'masked_number': f'•••• •••• •••• {card.last_four_digits}',
        'last_four_digits': card.last_four_digits,
        'card_source': card.card_source,
        'source_label': SOURCE_LABELS.get(card.card_source, card.card_source),
        'verification_status': card.verification_status,
        'is_verified': card.verification_status == VerificationStatus.VERIFIED,
        'provider_name': card.provider_name,
        'can_refresh': card.card_source == CardSource.PROVIDER and card.consent_id is not None,
        'can_edit_financials': card.card_source == CardSource.USER_ENTERED,
        'created_at': iso(card.created_at),
        'updated_at': iso(card.updated_at),
        **financials(card),
    }
    if detail and card.consent is not None:
        c = card.consent
        data['consent'] = {
            'consent_id': c.public_id, 'status': c.status, 'provider_name': c.provider_name,
            'purpose': c.purpose, 'data_scope': c.data_scope,
            'consent_expires_at': iso(c.consent_expires_at),
        }
    return data


def portfolio_summary(cards):
    """Aggregate only over cards that have the needed figures; say how many were counted."""
    with_limit = [c for c in cards if c.credit_limit is not None and c.outstanding_balance is not None]
    total_limit = sum((Decimal(c.credit_limit) for c in with_limit), Decimal('0'))
    total_out = sum((max(Decimal(c.outstanding_balance), Decimal('0')) for c in with_limit), Decimal('0'))
    upcoming = sorted([c for c in cards if c.due_date and (c.outstanding_balance or 0) > 0],
                      key=lambda c: c.due_date)
    nxt = upcoming[0] if upcoming else None
    return {
        'cards_count': len(cards),
        'cards_in_totals': len(with_limit),
        'total_credit_limit': cm.money(total_limit),
        'total_outstanding': cm.money(total_out),
        'overall_utilization_pct': cm.money(cm.utilization_pct(total_out, total_limit)),
        'verified_cards': sum(1 for c in cards if c.verification_status == VerificationStatus.VERIFIED),
        'next_due': {'card_id': nxt.public_id, 'card_nickname': nxt.card_nickname,
                     'due_date': nxt.due_date.isoformat(),
                     'outstanding_balance': cm.money(nxt.outstanding_balance)} if nxt else None,
    }


def record_snapshot(card, source, note=None):
    db.session.add(CardDataSnapshots(
        card_id=card.card_id, user_id=card.user_id, source=source, provider_name=card.provider_name,
        credit_limit=card.credit_limit, outstanding_balance=card.outstanding_balance,
        available_credit=card.available_credit, minimum_amount_due=card.minimum_amount_due,
        statement_date=card.statement_date, due_date=card.due_date,
        data_as_of=card.data_as_of, note=note,
    ))


def upsert_current_bill(card):
    """Keep exactly one current bill per card that mirrors the card's figures."""
    if card.due_date is None and card.outstanding_balance is None:
        return None
    bill = current_bill(card)
    if bill and bill.due_date != card.due_date:
        existing = Bills.query.filter_by(card_id=card.card_id, due_date=card.due_date).first()
        bill.is_current = False
        bill = existing
        if bill:
            bill.is_current = True
    if bill is None:
        bill = Bills(user_id=card.user_id, card_id=card.card_id, is_current=True)
        db.session.add(bill)
    bill.statement_date = card.statement_date
    bill.due_date = card.due_date
    bill.total_amount_due = card.outstanding_balance if (card.outstanding_balance or 0) >= 0 else Decimal('0')
    bill.minimum_amount_due = card.minimum_amount_due
    bill.source = card.card_source
    return bill


def apply_provider_data(card, data, provider):
    """Overwrite financial fields with validated provider data. Fields the provider
    did not supply become NULL — old user-entered guesses are not mixed in."""
    card.card_source = CardSource.PROVIDER
    card.verification_status = VerificationStatus.VERIFIED
    card.provider_name = provider.name
    card.provider_reference = data.provider_reference
    if data.card_network:
        card.card_network = data.card_network.upper()[:20]
    card.credit_limit = data.credit_limit
    card.outstanding_balance = data.outstanding_balance
    card.available_credit = data.available_credit
    card.minimum_amount_due = data.minimum_amount_due
    card.statement_date = data.statement_date
    card.due_date = data.due_date
    card.data_as_of = data.as_of
    card.updated_at = utcnow()
    db.session.flush()
    record_snapshot(card, CardSource.PROVIDER, note='provider sync')
    upsert_current_bill(card)
    for t in data.transactions:
        exists = CardTransactions.query.filter_by(card_id=card.card_id, provider_txn_ref=t.provider_txn_ref).first()
        if not exists:
            db.session.add(CardTransactions(
                card_id=card.card_id, user_id=card.user_id, provider_txn_ref=t.provider_txn_ref,
                txn_date=t.txn_date, description=(t.description or '')[:255] or None, amount=t.amount,
                txn_type=t.txn_type, txn_status=t.txn_status, source=CardSource.PROVIDER,
            ))
