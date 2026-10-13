from portal import db
from portal.models.roles import Roles
from portal.models.payment_gateways import PaymentGateways
from portal.models.user_sessions import UserSessions
from portal.models.users import Users

from .conftest import auth, login, manual_card


def as_role(app, sent_otps, mobile, role, name='Staff Member'):
    c, t = login(app, sent_otps, mobile=mobile, name=name)
    u = Users.query.filter_by(mobile_number='+91' + mobile).first()
    u.role_id = Roles.id_for(role)
    db.session.commit()
    return c, t


def test_new_signups_are_customers(app, sent_otps):
    c, t = login(app, sent_otps)
    me = c.get('/v1/authentication/me', headers=auth(t)).json['response']
    assert me['role'] == 'USER'


def test_role_enforced_on_server(app, sent_otps):
    cu, tu = login(app, sent_otps, mobile='9876543210')
    for path in ('/v1/admin/stats', '/v1/admin/users', '/v1/admin/gateways', '/v1/support/tickets'):
        assert cu.get(path, headers=auth(tu)).status_code == 403, path
    cs, ts = as_role(app, sent_otps, '9123456780', 'SUPPORT')
    assert cs.get('/v1/support/tickets', headers=auth(ts)).status_code == 200
    assert cs.get('/v1/admin/stats', headers=auth(ts)).status_code == 403
    # Staff accounts can't use customer card APIs as if they were customers.
    assert cs.get('/v1/cards', headers=auth(ts)).status_code == 403
    ca, ta = as_role(app, sent_otps, '9000000001', 'ADMIN')
    assert ca.get('/v1/admin/stats', headers=auth(ta)).status_code == 200
    assert ca.get('/v1/support/tickets', headers=auth(ta)).status_code == 200


def test_staff_without_pin_blocked(app, sent_otps):
    c, t = login(app, sent_otps, mobile='9000000001', pin=None)
    Users.query.filter_by(mobile_number='+919000000001').update({'role_id': Roles.id_for('ADMIN')})
    db.session.commit()
    assert c.get('/v1/admin/stats', headers=auth(t)).json['response']['code'] == 'PIN_REQUIRED'


def test_admin_changes_role_and_sessions_end(app, sent_otps):
    ca, ta = as_role(app, sent_otps, '9000000001', 'ADMIN')
    cu, tu = as_role(app, sent_otps, '9876543210', 'SUPPORT', name='Asha Rao')
    uid = cu.get('/v1/authentication/me', headers=auth(tu)).json['response']['user_id']
    r = ca.patch(f'/v1/admin/users/{uid}', json={'role': 'ADMIN'}, headers=auth(ta))
    assert r.status_code == 200 and r.json['response']['user']['role'] == 'ADMIN'
    assert cu.get('/v1/authentication/me', headers=auth(tu)).json['response']['code'] == 'SESSION_ENDED'


def test_admin_cannot_lock_self_out(app, sent_otps):
    ca, ta = as_role(app, sent_otps, '9000000001', 'ADMIN')
    me = ca.get('/v1/authentication/me', headers=auth(ta)).json['response']['user_id']
    r = ca.patch(f'/v1/admin/users/{me}', json={'role': 'SUPPORT'}, headers=auth(ta))
    assert r.status_code == 400 and r.json['response']['code'] == 'SELF_LOCKOUT'


def test_admin_invites_staff(app, sent_otps):
    ca, ta = as_role(app, sent_otps, '9000000001', 'ADMIN')
    body = {'mobile_number': '9811111111', 'role': 'SUPPORT', 'full_name': 'Priya S',
            'email': 'priya@cardvault.local', 'temporary_pin': '845203'}
    r = ca.post('/v1/admin/users', json=body, headers=auth(ta))
    assert r.status_code == 201 and r.json['response']['user']['role'] == 'SUPPORT'
    assert ca.post('/v1/admin/users', json=body, headers=auth(ta)).status_code == 409


def test_gateway_secrets_encrypted_and_masked(app, sent_otps):
    ca, ta = as_role(app, sent_otps, '9000000001', 'ADMIN')
    r = ca.post('/v1/admin/gateways', json={'display_name': 'Razorpay test', 'key_id': 'rzp_test_ABCDEF123',
                                            'key_secret': 'supersecretvalue1234', 'webhook_secret': 'hooksecret9876'},
                headers=auth(ta))
    assert r.status_code == 201
    g = r.json['response']['gateway']
    assert g['key_secret'] == '••••••1234' and 'supersecret' not in str(r.json)
    row = PaymentGateways.query.first()
    assert 'supersecret' not in row.encrypted_key_secret
    # Activating it makes payments use it instead of .env
    assert ca.patch(f"/v1/admin/gateways/{g['gateway_id']}", json={'is_active': True}, headers=auth(ta)).status_code == 200
    from portal.helpers.razorpay_helper import credentials
    c = credentials()
    assert c['source'] == 'ADMIN' and c['key_id'] == 'rzp_test_ABCDEF123' and c['key_secret'] == 'supersecretvalue1234'
    assert ca.delete(f"/v1/admin/gateways/{g['gateway_id']}", headers=auth(ta)).status_code == 400   # active
    bad = ca.post('/v1/admin/gateways', json={'display_name': 'x', 'key_id': 'nope', 'key_secret': 'abc'}, headers=auth(ta))
    assert bad.status_code == 400


def test_ticket_flow_user_support_and_privacy(app, sent_otps):
    cu, tu = login(app, sent_otps, mobile='9876543210', name='Asha Rao')
    card_id = manual_card(cu, tu).json['response']['card']['card_id']
    r = cu.post('/v1/tickets', json={'subject': 'Wrong due date', 'category': 'CARD', 'card_id': card_id,
                                     'message': 'My due date looks wrong.'}, headers=auth(tu))
    assert r.status_code == 201
    tid, ref = r.json['response']['ticket']['ticket_id'], r.json['response']['ticket']['reference']
    assert ref.startswith('CV-')

    cs, ts = as_role(app, sent_otps, '9123456780', 'SUPPORT', name='Priya Sharma')
    q = cs.get('/v1/support/tickets', headers=auth(ts)).json['response']
    assert [x['reference'] for x in q['items']] == [ref]
    detail = cs.get(f'/v1/support/tickets/{tid}', headers=auth(ts)).json['response']
    # Masked context only
    assert detail['customer']['mobile_number'].endswith('3210') and '9876543210' not in str(detail)
    assert detail['cards'][0]['masked_number'] == '•••• 4242'
    cs.post(f'/v1/support/tickets/{tid}/messages', json={'message': 'Internal: check issuer', 'internal': True}, headers=auth(ts))
    r = cs.post(f'/v1/support/tickets/{tid}/messages', json={'message': 'Please update it from Edit figures.'}, headers=auth(ts))
    assert r.json['response']['ticket']['status'] == 'WAITING_ON_USER'

    mine = cu.get(f'/v1/tickets/{tid}', headers=auth(tu)).json['response']['ticket']
    bodies = [m['body'] for m in mine['messages']]
    assert 'Internal: check issuer' not in bodies and 'Please update it from Edit figures.' in bodies

    # Another customer can't see or reply to it
    co, to = login(app, sent_otps, mobile='9811112222', name='Other User')
    assert co.get(f'/v1/tickets/{tid}', headers=auth(to)).status_code == 404
    assert co.post(f'/v1/tickets/{tid}/messages', json={'message': 'hi'}, headers=auth(to)).status_code == 404

    # Customer reply reopens; support resolves
    cu.post(f'/v1/tickets/{tid}/messages', json={'message': 'Done, thanks'}, headers=auth(tu))
    r = cs.patch(f'/v1/support/tickets/{tid}', json={'status': 'RESOLVED'}, headers=auth(ts))
    assert r.json['response']['ticket']['status'] == 'RESOLVED'


def test_support_lookup_is_masked_and_audited(app, sent_otps):
    from portal.models.audit_logs import AuditLogs
    cu, tu = login(app, sent_otps, mobile='9876543210', name='Asha Rao')
    manual_card(cu, tu)
    cs, ts = as_role(app, sent_otps, '9123456780', 'SUPPORT')
    r = cs.get('/v1/support/lookup?mobile=9876543210', headers=auth(ts))
    assert r.status_code == 200 and r.json['response']['cards'][0]['masked_number'] == '•••• 4242'
    assert 'credit_limit' not in r.json['response']['cards'][0]
    assert AuditLogs.query.filter_by(action='SUPPORT_LOOKUP').count() == 1
    # Staff accounts are not returned by customer lookup
    assert cs.get('/v1/support/lookup?mobile=9123456780', headers=auth(ts)).status_code == 404


def test_admin_stats_and_audit(app, sent_otps):
    cu, tu = login(app, sent_otps, mobile='9876543210')
    manual_card(cu, tu)
    ca, ta = as_role(app, sent_otps, '9000000001', 'ADMIN')
    s = ca.get('/v1/admin/stats', headers=auth(ta)).json['response']
    assert s['cards']['active'] == 1 and s['users']['by_role']['ADMIN'] == 1
    logs = ca.get('/v1/admin/audit-logs', headers=auth(ta)).json['response']
    assert any(x['action'] == 'CARD_ADDED_MANUAL' for x in logs['items'])
    iss = ca.get('/v1/admin/issuers', headers=auth(ta)).json['response']['issuers']
    hdfc = next(i for i in iss if i['code'] == 'HDFC')
    assert hdfc['cards'] == 1
    r = ca.patch(f"/v1/admin/issuers/{hdfc['issuer_id']}", json={'is_active': False}, headers=auth(ta))
    assert r.status_code == 200
    codes = [i['code'] for i in cu.get('/v1/cards/issuers', headers=auth(tu)).json['response']['issuers']]
    assert 'HDFC' not in codes
