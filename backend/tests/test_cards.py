from portal.models.audit_logs import AuditLogs
from portal.models.card_data_snapshots import CardDataSnapshots

from .conftest import auth, issuer_id, login, manual_card


def test_add_manual_card_and_see_it_on_dashboard(app, sent_otps):
    c, t = login(app, sent_otps)
    r = manual_card(c, t)
    assert r.status_code == 201, r.json
    card = r.json['response']['card']
    assert card['card_source'] == 'USER_ENTERED'
    assert card['source_label'] == 'User-entered — Not Bank Verified'
    assert card['is_verified'] is False
    assert card['masked_number'].endswith('4242') and '4242' == card['last_four_digits']
    assert card['utilization_pct'] == '22.50'
    assert card['available_credit'] == '154999.50' and card['available_credit_basis'] == 'ESTIMATED'

    listing = c.get('/v1/cards', headers=auth(t)).json['response']
    assert [x['card_id'] for x in listing['cards']] == [card['card_id']]
    assert listing['summary']['total_credit_limit'] == '200000.00'
    assert CardDataSnapshots.query.count() == 1


def test_reported_available_credit_wins(app, sent_otps):
    c, t = login(app, sent_otps)
    card = manual_card(c, t, available_credit='150000').json['response']['card']
    assert card['available_credit'] == '150000.00' and card['available_credit_basis'] == 'REPORTED'


def test_invalid_card_data_rejected(app, sent_otps):
    c, t = login(app, sent_otps)
    cases = [
        ({'last_four_digits': '42a2'}, 'last_four_digits'),
        ({'last_four_digits': '42424'}, 'last_four_digits'),
        ({'credit_limit': '-100'}, 'credit_limit'),
        ({'credit_limit': '0'}, 'credit_limit'),
        ({'credit_limit': '100.123'}, 'credit_limit'),
        ({'outstanding_balance': 'abc'}, 'outstanding_balance'),
        ({'minimum_amount_due': '50000'}, 'minimum_amount_due'),
        ({'available_credit': '300000'}, 'available_credit'),
        ({'billing_day': 32}, 'billing_day'),
        ({'due_date': '2020-01-01'}, 'due_date'),
        ({'due_date': '31-12-2026'}, 'due_date'),
        ({'card_nickname': ''}, 'card_nickname'),
        ({'card_network': 'BITCOIN'}, 'card_network'),
        ({'issuer_id': 99999}, 'issuer_id'),
    ]
    for over, field in cases:
        r = manual_card(c, t, **over)
        assert r.status_code == 400, (over, r.json)
        assert field in r.json['response']['errors'], (over, r.json)


def test_other_bank_requires_name(app, sent_otps):
    c, t = login(app, sent_otps)
    other = issuer_id(c, t, 'OTHER')
    assert manual_card(c, t, issuer_id=other).status_code == 400
    r = manual_card(c, t, issuer_id=other, issuer_name='Saraswat Bank')
    assert r.status_code == 201 and r.json['response']['card']['issuer_name'] == 'Saraswat Bank'


def test_sensitive_fields_are_refused_not_stored(app, sent_otps):
    c, t = login(app, sent_otps)
    for field in ('card_number', 'cvv', 'otp', 'expiry'):
        r = manual_card(c, t, **{field: '4111111111111111'})
        assert r.status_code == 400 and r.json['response']['code'] == 'SENSITIVE_DATA_REJECTED'
    assert c.get('/v1/cards', headers=auth(t)).json['response']['cards'] == []


def test_duplicate_card_rejected_and_readd_after_removal(app, sent_otps):
    c, t = login(app, sent_otps)
    first = manual_card(c, t).json['response']['card']
    r = manual_card(c, t, card_nickname='Another name')
    assert r.status_code == 409 and r.json['response']['code'] == 'DUPLICATE_CARD'
    assert manual_card(c, t, last_four_digits='1111').status_code == 201
    assert c.delete(f"/v1/cards/{first['card_id']}", headers=auth(t)).status_code == 200
    assert manual_card(c, t).status_code == 201


def test_user_cannot_access_another_users_card(app, sent_otps):
    ca, ta = login(app, sent_otps, mobile='9876543210')
    card_id = manual_card(ca, ta).json['response']['card']['card_id']
    cb, tb = login(app, sent_otps, mobile='9123456780', name='Ravi Kumar')
    for method, path in (('get', ''), ('get', '/summary'), ('get', '/payments'), ('get', '/transactions'),
                         ('post', '/refresh'), ('patch', ''), ('delete', '')):
        r = getattr(cb, method)(f'/v1/cards/{card_id}{path}', json={'card_nickname': 'pwned'}, headers=auth(tb))
        assert r.status_code == 404, (method, path, r.status_code)
    assert cb.get('/v1/cards', headers=auth(tb)).json['response']['cards'] == []
    # Owner still has it, untouched.
    assert ca.get(f'/v1/cards/{card_id}', headers=auth(ta)).json['response']['card']['card_nickname'] == 'Regalia'


def test_remove_card_owner_only_and_data_erased(app, sent_otps):
    c, t = login(app, sent_otps)
    card_id = manual_card(c, t).json['response']['card']['card_id']
    assert c.delete(f'/v1/cards/{card_id}', headers=auth(t)).status_code == 200
    assert c.get(f'/v1/cards/{card_id}', headers=auth(t)).status_code == 404
    assert c.delete(f'/v1/cards/{card_id}', headers=auth(t)).status_code == 404
    assert CardDataSnapshots.query.count() == 0
    assert AuditLogs.query.filter_by(action='CARD_REMOVED').count() == 1


def test_edit_manual_card_figures(app, sent_otps):
    c, t = login(app, sent_otps)
    card_id = manual_card(c, t).json['response']['card']['card_id']
    r = c.patch(f'/v1/cards/{card_id}', json={'outstanding_balance': '0', 'minimum_amount_due': '0'},
                headers=auth(t))
    assert r.status_code == 200
    card = r.json['response']['card']
    assert card['utilization_pct'] == '0.00' and card['bill_status'] == 'NO_DUES'
    r = c.patch(f'/v1/cards/{card_id}', json={'minimum_amount_due': '10'}, headers=auth(t))
    assert r.status_code == 400   # cross-checked against stored outstanding of 0


def test_manual_card_has_no_bank_transactions_and_cannot_refresh(app, sent_otps):
    c, t = login(app, sent_otps)
    card_id = manual_card(c, t).json['response']['card']['card_id']
    r = c.get(f'/v1/cards/{card_id}/transactions', headers=auth(t)).json['response']
    assert r['available'] is False and r['transactions'] == []
    r = c.post(f'/v1/cards/{card_id}/refresh', headers=auth(t))
    assert r.status_code == 400 and r.json['response']['code'] == 'REFRESH_NOT_SUPPORTED'


def test_bank_linking_not_configured(app, sent_otps):
    c, t = login(app, sent_otps)
    cfg = c.get('/v1/cards/link/config', headers=auth(t)).json['response']
    assert cfg['configured'] is False and 'not configured' in cfg['message']
    r = c.post('/v1/cards/link-session', json={'issuer_id': issuer_id(c, t), 'consent_acknowledged': True},
               headers=auth(t))
    assert r.status_code == 503 and r.json['response']['code'] == 'INTEGRATION_NOT_CONFIGURED'
    # Manual entry still works.
    assert manual_card(c, t).status_code == 201


def test_issuers_list(app, sent_otps):
    c, t = login(app, sent_otps)
    codes = [i['code'] for i in c.get('/v1/cards/issuers', headers=auth(t)).json['response']['issuers']]
    assert {'SBI', 'HDFC', 'ICICI', 'AXIS'} <= set(codes) and codes[-1] == 'OTHER'


def test_errors_do_not_leak_internals(app, sent_otps, monkeypatch):
    c, t = login(app, sent_otps)

    def boom(*a, **k):
        raise RuntimeError('SELECT * FROM secret_table password=hunter2')
    monkeypatch.setattr('portal.helpers.card_service.record_snapshot', boom)
    r = manual_card(c, t)
    assert r.status_code == 500
    assert 'hunter2' not in r.get_data(as_text=True) and 'SELECT' not in r.get_data(as_text=True)
