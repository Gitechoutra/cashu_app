"""
Account Aggregator (AA) adapter — configuration scaffold, intentionally NOT wired
to any URL.

In India, consented access to a user's financial data goes through the RBI
Account Aggregator framework (ReBIT specifications). Your app would act as a
Financial Information User (FIU), usually via a licensed AA or a technology
service provider. Each partner has its own API, request signing, consent
templates and FIP (bank) coverage — and credit-card FI data is not offered by
every bank (FIP). Nothing here assumes a particular partner.

To enable:
  1. Sign up with an AA / FIU-TSP partner; complete their onboarding and approval.
  2. Implement every method below strictly from that partner's official docs.
  3. Fill card_issuers.provider_institution_id with the partner's FIP ids for
     banks that actually publish credit-card data.
  4. Set CARD_DATA_PROVIDER=account_aggregator and the AA_* variables in .env.

Until then is_configured() returns False and the app shows
"Bank integration not configured" while manual entry keeps working.
"""

import os

from .base import CardDataProvider, ProviderNotConfigured


class AccountAggregatorProvider(CardDataProvider):
    name = 'account_aggregator'
    display_name = 'Account Aggregator'

    # Set to True only after the methods below are implemented from partner docs.
    IMPLEMENTED = False

    def is_configured(self):
        return self.IMPLEMENTED and all(os.getenv(k) for k in ('AA_CLIENT_ID', 'AA_CLIENT_SECRET', 'AA_BASE_URL'))

    def capabilities(self):
        # Fill in from the partner's documented FI data schema — do not guess.
        return {}

    def institution_ids(self):
        return {}

    def _nope(self, *a, **k):
        raise ProviderNotConfigured()

    create_link_session = _nope
    exchange_callback = _nope
    fetch_supported_card_data = _nope
    refresh_card_data = _nope
    revoke_link = _nope

    def verify_webhook(self, *, headers, raw_body):
        return False
