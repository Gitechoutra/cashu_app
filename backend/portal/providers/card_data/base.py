"""
Card-data provider interface.

These are INTERNAL adapter methods. They are not endpoints of any bank. A concrete
adapter implements them against one authorised provider's official, documented
API (for India, typically an RBI-licensed Account Aggregator via a FIU/TSP partner).
Different providers expose different data — capabilities() must report exactly
what the integrated provider supplies, and nothing is filled in when it doesn't.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional


# ── Errors ──────────────────────────────────────────────────────────────────

class ProviderError(Exception):
    code = 'PROVIDER_ERROR'
    http_status = 502
    user_message = 'The bank data provider returned an error. Please try again later.'


class ProviderNotConfigured(ProviderError):
    code = 'INTEGRATION_NOT_CONFIGURED'
    http_status = 503
    user_message = 'Bank integration not configured. You can still add your card manually.'


class ConsentExpired(ProviderError):
    code = 'CONSENT_EXPIRED'
    http_status = 409
    user_message = 'Your data-sharing consent has expired. Re-link the card to refresh it.'


class ConsentRevoked(ProviderError):
    code = 'CONSENT_REVOKED'
    http_status = 409
    user_message = 'Data-sharing consent was revoked. Re-link the card to continue.'


class RateLimited(ProviderError):
    code = 'PROVIDER_RATE_LIMITED'
    http_status = 429
    user_message = 'The bank data provider is busy. Please try again in a few minutes.'


class DataUnavailable(ProviderError):
    code = 'DATA_UNAVAILABLE'
    http_status = 424
    user_message = 'Your bank did not provide credit card data through this integration.'


class InvalidProviderResponse(ProviderError):
    code = 'INVALID_PROVIDER_RESPONSE'
    user_message = 'The bank data could not be verified, so it was not saved.'


# ── Data contracts ──────────────────────────────────────────────────────────

@dataclass
class LinkSessionResult:
    redirect_url: str                       # provider-hosted consent/authentication page
    provider_session_ref: Optional[str] = None


@dataclass
class CallbackResult:
    status: str                             # 'ACTIVE' | 'REJECTED' | 'PENDING'
    consent_reference: Optional[str] = None
    access_token: Optional[str] = None      # encrypted before storage; never sent to the browser
    token_expires_at: Optional[datetime] = None
    consent_expires_at: Optional[datetime] = None
    data_scope: List[str] = field(default_factory=list)


@dataclass
class ProviderTransaction:
    provider_txn_ref: str
    txn_date: date
    amount: Decimal
    txn_type: str                           # DEBIT | CREDIT
    description: Optional[str] = None
    txn_status: str = 'POSTED'


@dataclass
class ProviderCardData:
    provider_reference: str                 # opaque account reference at the provider
    last_four_digits: str
    as_of: datetime                         # when the provider says the figures were true
    issuer_name: Optional[str] = None
    card_network: Optional[str] = None
    currency: str = 'INR'
    # Every figure is Optional — None means "provider did not supply it".
    credit_limit: Optional[Decimal] = None
    outstanding_balance: Optional[Decimal] = None
    available_credit: Optional[Decimal] = None
    minimum_amount_due: Optional[Decimal] = None
    statement_date: Optional[date] = None
    due_date: Optional[date] = None
    transactions: List[ProviderTransaction] = field(default_factory=list)


# ── Interface ───────────────────────────────────────────────────────────────

class CardDataProvider(ABC):
    name = 'base'
    display_name = 'Provider'

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def capabilities(self) -> dict:
        """e.g. {'credit_limit': True, 'outstanding_balance': True, 'available_credit': False,
        'minimum_amount_due': True, 'due_date': True, 'transactions': True, 'refresh': True}"""

    @abstractmethod
    def institution_ids(self) -> dict:
        """{issuer_code: provider_institution_id} for banks this provider actually supports."""

    @abstractmethod
    def create_link_session(self, *, user_ref: str, institution_id: str, state: str,
                            redirect_uri: str, purpose: str) -> LinkSessionResult: ...

    @abstractmethod
    def exchange_callback(self, *, params: dict) -> CallbackResult:
        """Validate the provider redirect / result (signature, status) per provider docs.
        `state` has already been matched to the link session by the caller."""

    @abstractmethod
    def verify_webhook(self, *, headers: dict, raw_body: bytes) -> bool: ...

    def parse_webhook(self, *, raw_body: bytes) -> List[dict]:
        """Translate a VERIFIED webhook into consent updates:
        [{'consent_reference': str, 'status': 'ACTIVE'|'REVOKED'|'EXPIRED'|'REJECTED'}]"""
        return []

    @abstractmethod
    def fetch_supported_card_data(self, *, access_token: str) -> List[ProviderCardData]: ...

    @abstractmethod
    def refresh_card_data(self, *, access_token: str, provider_reference: str) -> ProviderCardData: ...

    @abstractmethod
    def revoke_link(self, *, access_token: str, consent_reference: str) -> None: ...
