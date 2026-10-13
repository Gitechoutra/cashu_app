"""Resolves the configured card-data provider and validates everything it returns
before it can touch the database."""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import current_app

from portal.models.base import utcnow

from .base import InvalidProviderResponse, ProviderCardData

_PROVIDERS = {}
_override = None          # tests only — see set_test_provider()


def register(cls):
    _PROVIDERS[cls.name] = cls
    return cls


def _load_builtin():
    from .account_aggregator import AccountAggregatorProvider
    register(AccountAggregatorProvider)


def get_provider():
    """Return a configured provider instance, or None when bank linking is unavailable."""
    if _override is not None:
        return _override
    if not _PROVIDERS:
        _load_builtin()
    cls = _PROVIDERS.get(current_app.config.get('CARD_DATA_PROVIDER') or '')
    if cls is None:
        return None
    inst = cls()
    return inst if inst.is_configured() else None


def set_test_provider(provider):
    """Inject a fake provider. Refuses outside TESTING so mock data can never reach users."""
    global _override
    if provider is not None and not current_app.config.get('TESTING'):
        raise RuntimeError('Test providers are only allowed when TESTING is enabled.')
    _override = provider


# ── Response validation ─────────────────────────────────────────────────────

_MAX = Decimal('9999999999.99')


def _money(v, label, allow_negative=False):
    if v is None:
        return None
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        raise InvalidProviderResponse(f'{label} not numeric')
    if not d.is_finite() or abs(d) > _MAX or d != d.quantize(Decimal('0.01')):
        raise InvalidProviderResponse(f'{label} out of range / precision')
    if d < 0 and not allow_negative:
        raise InvalidProviderResponse(f'{label} negative')
    return d


def validate_card_data(item: ProviderCardData) -> ProviderCardData:
    if not isinstance(item, ProviderCardData):
        raise InvalidProviderResponse('unexpected type')
    if not item.provider_reference or len(item.provider_reference) > 128:
        raise InvalidProviderResponse('bad provider_reference')
    if not re.fullmatch(r'\d{4}', str(item.last_four_digits or '')):
        raise InvalidProviderResponse('bad last_four_digits')
    if (item.currency or '').upper() != 'INR':
        raise InvalidProviderResponse('unsupported currency')
    if not isinstance(item.as_of, datetime) or item.as_of > utcnow() + timedelta(minutes=5):
        raise InvalidProviderResponse('bad as_of timestamp')
    item.credit_limit = _money(item.credit_limit, 'credit_limit')
    item.outstanding_balance = _money(item.outstanding_balance, 'outstanding_balance', allow_negative=True)
    item.available_credit = _money(item.available_credit, 'available_credit', allow_negative=True)
    item.minimum_amount_due = _money(item.minimum_amount_due, 'minimum_amount_due')
    for d in (item.statement_date, item.due_date):
        if d is not None and not isinstance(d, date):
            raise InvalidProviderResponse('bad date')
    for t in item.transactions:
        if not t.provider_txn_ref or t.txn_type not in ('DEBIT', 'CREDIT') or not isinstance(t.txn_date, date):
            raise InvalidProviderResponse('bad transaction')
        t.amount = _money(t.amount, 'transaction amount')
    return item
