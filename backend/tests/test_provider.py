"""Bank-linking flow against an in-process FAKE provider (tests only — the
registry refuses fakes outside TESTING). Nothing here is presented as bank data."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from portal.models.base import utcnow

from portal.models.financial_consents import FinancialConsents
from portal.models.linked_cards import LinkedCards
from portal.providers.card_data import registry
from portal.providers.card_data.base import (
    CallbackResult, CardDataProvider, ConsentExpired, LinkSessionResult, ProviderCardData,
    ProviderTransaction, RateLimited,
)

from .conftest import auth, issuer_id, login, manual_card


class FakeProvider(CardDataProvider):
    name = 'fake'
    display_name = 'Fake AA (tests)'

    def __init__(self):
        self.cards = [self.card()]
        self.refresh_error = None
        self.revoked = []

    @staticmethod
    def card(**over):
        d = dict(provider_reference='acct-1', last_four_digits='4242', as_of=utcnow() - timedelta(minutes=5),
                 credit_limit=Decimal('300000.00'), outstanding_balance=Decimal('60000.00'),
                 available_credit=Decimal('235000.00'), minimum_amount_due=Decimal('3000.00'),
                 statement_date=date.today() - timedelta(days=5), due_date=date.today() + timedelta(days=15),
                 transactions=[ProviderTransaction('t1', date.today(), Decimal('1200.00'), 'DEBIT', 'Groceries')])
        d.update(over)
        return ProviderCardData(**d)

    def is_configured(self): return True
    def capabilities(self): return {'credit_limit': True, 'outstanding_balance': True, 'transactions': True, 'refresh': True}
    def institution_ids(self): return {'HDFC': 'fip-hdfc'}

    def create_link_session(self, *, user_ref, institution_id, state, redirect_uri, purpose):
        self.state = state
        return LinkSessionResult(redirect_url=f'https://provider.invalid/consent?s={state}', provider_session_ref='ps1')

    def exchange_callback(self, *, params):
        if params.get('status') == 'rejected':
            return CallbackResult(status='REJECTED')
        return CallbackResult(status='ACTIVE', consent_reference='c-1', access_token='tok-secret',
                              consent_expires_at=utcnow() + timedelta(days=180))

    def verify_webhook(self, *, headers, raw_body): return headers.get('X-Fake-Sig') == 'ok'
    def parse_webhook(self, *, raw_body): return [{'consent_reference': 'c-1', 'status': 'REVOKED'}]
    def fetch_supported_card_data(self, *, access_token):
        assert access_token == 'tok-secret'
        return self.cards

    def refresh_card_data(self, *, access_token, provider_reference):
        if self.refresh_error:
            raise self.refresh_error
        return self.card(outstanding_balance=Decimal('10000.00'), available_credit=None)

    def revoke_link(self, *, access_token, consent_reference): self.revoked.append(consent_reference)


@pytest.fixture
def fake(app):
    p = FakeProvider()
    registry.set_test_provider(p)
    return p


def _link(c, t, fake, status='granted'):
    r = c.post('/v1/cards/link-session', json={'issuer_id': issuer_id(c, t), 'consent_acknowledged': True},
               headers=auth(t))
    assert r.status_code == 201, r.json
    sid = r.json['response']['session_id']
    cb = c.get(f'/v1/cards/link/callback?state={fake.state}&status={status}')
    assert cb.status_code == 302
    return sid, cb


def test_link_flow_creates_verified_card(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    sid, cb = _link(c, t, fake)
    assert parse_qs(urlparse(cb.location).query)['link_session'] == [sid]
    st = c.get(f'/v1/cards/link-status/{sid}', headers=auth(t)).json['response']
    assert st['status'] == 'COMPLETED' and st['cards_linked'] == 1

    card = c.get('/v1/cards', headers=auth(t)).json['response']['cards'][0]
    assert card['card_source'] == 'PROVIDER' and card['is_verified'] and card['source_label'] == 'Provider-verified'
    assert card['available_credit'] == '235000.00' and card['available_credit_basis'] == 'REPORTED'
    txns = c.get(f"/v1/cards/{card['card_id']}/transactions", headers=auth(t)).json['response']
    assert txns['available'] and txns['transactions'][0]['amount'] == '1200.00'
    # Token is encrypted at rest and never returned to the client.
    consent = FinancialConsents.query.first()
    assert consent.encrypted_access_token and 'tok-secret' not in consent.encrypted_access_token
    assert 'tok-secret' not in str(c.get(f"/v1/cards/{card['card_id']}", headers=auth(t)).json)


def test_link_requires_consent_ack_and_supported_issuer(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    r = c.post('/v1/cards/link-session', json={'issuer_id': issuer_id(c, t)}, headers=auth(t))
    assert r.json['response']['code'] == 'CONSENT_REQUIRED'
    r = c.post('/v1/cards/link-session', json={'issuer_id': issuer_id(c, t, 'SBI'), 'consent_acknowledged': True},
               headers=auth(t))
    assert r.status_code == 422 and r.json['response']['code'] == 'ISSUER_NOT_SUPPORTED'


def test_callback_with_bad_state_is_rejected(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    c.post('/v1/cards/link-session', json={'issuer_id': issuer_id(c, t), 'consent_acknowledged': True}, headers=auth(t))
    cb = c.get('/v1/cards/link/callback?state=forged')
    assert 'link_error=invalid_state' in cb.location
    assert LinkedCards.query.count() == 0


def test_link_status_is_owner_only(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    sid, _ = _link(c, t, fake)
    c2, t2 = login(app, sent_otps, mobile='9123456780')
    assert c2.get(f'/v1/cards/link-status/{sid}', headers=auth(t2)).status_code == 404


def test_rejected_consent_creates_nothing(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    sid, _ = _link(c, t, fake, status='rejected')
    assert c.get(f'/v1/cards/link-status/{sid}', headers=auth(t)).json['response']['status'] == 'FAILED'
    assert LinkedCards.query.count() == 0


def test_invalid_provider_data_is_not_saved(app, sent_otps, fake):
    fake.cards = [FakeProvider.card(credit_limit=Decimal('-5'))]
    c, t = login(app, sent_otps)
    sid, _ = _link(c, t, fake)
    st = c.get(f'/v1/cards/link-status/{sid}', headers=auth(t)).json['response']
    assert st['status'] == 'FAILED' and st['error_code'] == 'INVALID_PROVIDER_RESPONSE'
    assert LinkedCards.query.count() == 0


def test_missing_fields_stay_unknown(app, sent_otps, fake):
    fake.cards = [FakeProvider.card(credit_limit=None, available_credit=None)]
    c, t = login(app, sent_otps)
    _link(c, t, fake)
    card = c.get('/v1/cards', headers=auth(t)).json['response']['cards'][0]
    assert card['credit_limit'] is None and card['utilization_pct'] is None
    assert card['available_credit_basis'] == 'UNKNOWN'


def test_linking_upgrades_matching_manual_card(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    manual_card(c, t)       # HDFC ••4242 user-entered
    _link(c, t, fake)
    cards = c.get('/v1/cards', headers=auth(t)).json['response']['cards']
    assert len(cards) == 1 and cards[0]['card_source'] == 'PROVIDER'


def test_provider_figures_cannot_be_overwritten_by_client(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    _link(c, t, fake)
    card_id = c.get('/v1/cards', headers=auth(t)).json['response']['cards'][0]['card_id']
    r = c.patch(f'/v1/cards/{card_id}', json={'credit_limit': '9999999'}, headers=auth(t))
    assert r.status_code == 403 and r.json['response']['code'] == 'PROVIDER_DATA_READ_ONLY'
    assert c.patch(f'/v1/cards/{card_id}', json={'card_nickname': 'Infinia'}, headers=auth(t)).status_code == 200


def test_refresh_success_and_expired_consent(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    _link(c, t, fake)
    card_id = c.get('/v1/cards', headers=auth(t)).json['response']['cards'][0]['card_id']
    r = c.post(f'/v1/cards/{card_id}/refresh', headers=auth(t))
    assert r.status_code == 200 and r.json['response']['card']['outstanding_balance'] == '10000.00'
    assert r.json['response']['card']['available_credit_basis'] == 'ESTIMATED'

    fake.refresh_error = RateLimited()
    r = c.post(f'/v1/cards/{card_id}/refresh', headers=auth(t))
    assert r.status_code == 429 and 'last verified' in r.json['response']['message']

    fake.refresh_error = ConsentExpired()
    r = c.post(f'/v1/cards/{card_id}/refresh', headers=auth(t))
    assert r.status_code == 409 and r.json['response']['code'] == 'CONSENT_EXPIRED'
    card = c.get(f'/v1/cards/{card_id}', headers=auth(t)).json['response']['card']
    assert card['verification_status'] == 'CONSENT_EXPIRED' and card['is_verified'] is False
    assert FinancialConsents.query.first().encrypted_access_token is None


def test_revoke_consent_and_remove_card(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    _link(c, t, fake)
    consent_id = c.get('/v1/cards/consents', headers=auth(t)).json['response']['consents'][0]['consent_id']
    assert c.post(f'/v1/cards/consents/{consent_id}/revoke', headers=auth(t)).status_code == 200
    assert fake.revoked == ['c-1']
    card = c.get('/v1/cards', headers=auth(t)).json['response']['cards'][0]
    assert card['verification_status'] == 'CONSENT_REVOKED'
    assert c.post(f"/v1/cards/{card['card_id']}/refresh", headers=auth(t)).status_code == 409


def test_link_webhook_requires_signature(app, sent_otps, fake):
    c, t = login(app, sent_otps)
    _link(c, t, fake)
    assert c.post('/v1/cards/link/webhook', data=b'{}').status_code == 401
    assert c.post('/v1/cards/link/webhook', data=b'{}', headers={'X-Fake-Sig': 'ok'}).status_code == 200
    assert FinancialConsents.query.first().status == 'REVOKED'


def test_fake_provider_refused_outside_testing(app):
    app.config['TESTING'] = False
    try:
        with pytest.raises(RuntimeError):
            registry.set_test_provider(FakeProvider())
    finally:
        app.config['TESTING'] = True
