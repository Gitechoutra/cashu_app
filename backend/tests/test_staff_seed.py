"""Staff accounts defined in seeders/seed_admin.py and seeders/seed_customersupport.py."""

from werkzeug.security import check_password_hash

from portal import db
from portal.models.audit_logs import AuditLogs
from portal.models.roles import Roles
from portal.models.user_sessions import UserSessions
from portal.models.users import Users
from portal.seeders import seed_admin as sa, seed_customersupport as sc

from .conftest import H, auth, login, new_client

ADMIN_PIN, NEW_PIN, AGENT_PIN = '482617', '731940', '593174'


def admin_entry(**over):
    e = {'key': 'primary_admin', 'email': 'admin@cardvault.local', 'mobile_number': '9000000001',
         'full_name': 'CardVault Admin', 'pin': ADMIN_PIN}
    e.update(over)
    return e


AGENT = {'key': 'support_agent_1', 'email': 'support@cardvault.local', 'mobile_number': '9000000002',
         'full_name': 'Support Agent', 'pin': AGENT_PIN}


def run(monkeypatch, admins=None, agents=None):
    if admins is not None:
        monkeypatch.setattr(sa, 'ADMINS', admins)
    if agents is not None:
        monkeypatch.setattr(sc, 'SUPPORT_AGENTS', agents)
    return sa.seed_admin(), sc.seed_customer_support()


def get(key):
    return Users.query.filter_by(seed_key=key).first()


def staff_login(app, email='admin@cardvault.local', pin=ADMIN_PIN, role=None):
    c = new_client(app)
    r = c.post('/v1/authentication/staff/login', json={'email': email, 'pin': pin, 'role': role}, headers=H)
    return c, r


def test_creates_admin_and_support_with_hashed_pins(app, monkeypatch):
    run(monkeypatch, [admin_entry()], [dict(AGENT)])
    a, s = get('primary_admin'), get('support_agent_1')
    assert a.role_name == 'ADMIN' and s.role_name == 'SUPPORT'
    assert a.email == 'admin@cardvault.local' and a.mobile_number == '+919000000001'
    assert check_password_hash(a.pin_hash, ADMIN_PIN) and ADMIN_PIN not in a.pin_hash
    assert check_password_hash(s.pin_hash, AGENT_PIN)


def test_editing_file_updates_database(app, monkeypatch):
    run(monkeypatch, [admin_entry()])
    uid = get('primary_admin').user_id
    run(monkeypatch, [admin_entry(email='head@cardvault.local', mobile_number='9811122233', full_name='Head Admin', pin=NEW_PIN)])
    a = get('primary_admin')
    assert a.user_id == uid
    assert (a.email, a.mobile_number, a.full_name) == ('head@cardvault.local', '+919811122233', 'Head Admin')
    assert check_password_hash(a.pin_hash, NEW_PIN)
    log = AuditLogs.query.filter_by(action='STAFF_SEED_UPDATED').one()
    assert sorted(log.details['changed']) == ['email', 'full_name', 'mobile_number', 'pin']
    assert NEW_PIN not in str(log.details)


def test_unchanged_file_is_a_no_op(app, monkeypatch):
    run(monkeypatch, [admin_entry()])
    assert run(monkeypatch, [admin_entry()])[0] == '0 created, 0 updated, 0 suspended'


def test_seeded_admin_signs_in_with_email_and_is_signed_out_when_pin_changes(app, monkeypatch):
    run(monkeypatch, [admin_entry()])
    c, r = staff_login(app)
    body = r.json['response']
    assert r.status_code == 200 and body['user']['role'] == 'ADMIN' and body['pin_reset_required'] is False
    t = body['access_token']
    assert c.get('/v1/admin/stats', headers=auth(t)).status_code == 200
    run(monkeypatch, [admin_entry(pin=NEW_PIN)])
    assert c.get('/v1/admin/stats', headers=auth(t)).json['response']['code'] == 'SESSION_ENDED'


def test_removed_entry_is_suspended_and_restored(app, monkeypatch):
    run(monkeypatch, agents=[dict(AGENT)])
    run(monkeypatch, agents=[])
    assert get('support_agent_1').status == 'SUSPENDED'
    run(monkeypatch, agents=[dict(AGENT)])
    assert get('support_agent_1').status == 'ACTIVE'


def test_invalid_entries_are_skipped(app, monkeypatch):
    summary = run(monkeypatch, [admin_entry(pin='1234'), admin_entry(key='b', pin='123456'), admin_entry(key='c', pin=''),
                                admin_entry(key='d', email='bad'), admin_entry(key='e', mobile_number='123')])[0]
    assert '5 skipped' in summary and Users.query.count() == 0


def test_customer_account_is_never_adopted(app, sent_otps, monkeypatch):
    login(app, sent_otps, mobile='9000000003', name='Ravi Kumar')
    summary = run(monkeypatch, [admin_entry(key='second_admin', mobile_number='9000000003', email='ravi@cardvault.local')])[0]
    assert '1 skipped' in summary
    assert Users.query.filter_by(mobile_number='+919000000003').one().role_name == 'USER'


def test_in_app_edits_blocked_for_seed_managed(app, sent_otps, monkeypatch):
    run(monkeypatch, [admin_entry()])
    c, r = staff_login(app)
    t = r.json['response']['access_token']
    r = c.post('/v1/security/pin', json={'current_pin': ADMIN_PIN, 'new_pin': NEW_PIN}, headers=auth(t))
    assert r.status_code == 403 and r.json['response']['code'] == 'MANAGED_BY_SEED'
    assert c.patch('/v1/authentication/me', json={'full_name': 'Someone Else'}, headers=auth(t)).status_code == 403
    uid = get('primary_admin').public_id
    c2, t2 = login(app, sent_otps, mobile='9811111111', name='Other Admin')
    Users.query.filter_by(mobile_number='+919811111111').update({'role_id': Roles.id_for('ADMIN')})
    db.session.commit()
    r = c2.patch(f'/v1/admin/users/{uid}', json={'role': 'SUPPORT'}, headers=auth(t2))
    assert r.status_code == 409 and r.json['response']['code'] == 'MANAGED_BY_SEED'
