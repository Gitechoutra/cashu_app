"""
Razorpay integration using the documented REST API (https://razorpay.com/docs/api/):
  POST /v1/orders                 — create an order
  GET  /v1/payments/{id}          — fetch a payment (server-side confirmation)
  GET  /v1/orders/{id}/payments   — reconcile all attempts on an order
Checkout signature:  HMAC_SHA256(order_id + "|" + payment_id, key_secret)
Webhook signature:   HMAC_SHA256(raw_body, webhook_secret) in X-Razorpay-Signature

Keys are read from config (.env) only; the key *secret* never leaves the server.
"""

import hashlib
import hmac
import logging

import requests
from flask import current_app

logger = logging.getLogger('cardvault.razorpay')
TIMEOUT = 15


class RazorpayError(Exception):
    pass


def credentials():
    """Active gateway credentials: the Admin-managed `payment_gateways` row wins,
    falling back to .env. Secrets stay server-side."""
    cfg = current_app.config
    try:
        from portal.helpers.encryption import decrypt
        from portal.models.payment_gateways import PaymentGateways
        gw = PaymentGateways.query.filter_by(is_active=True, provider='RAZORPAY').first()
        if gw:
            return {'key_id': gw.key_id, 'key_secret': decrypt(gw.encrypted_key_secret),
                    'webhook_secret': decrypt(gw.encrypted_webhook_secret) if gw.encrypted_webhook_secret else '',
                    'source': 'ADMIN'}
    except Exception as e:                       # table missing / key rotated → fall back to .env
        from portal import db
        db.session.rollback()
        logger.warning(f'Gateway config from DB unavailable ({e.__class__.__name__}); using .env')
    return {'key_id': cfg.get('RAZORPAY_KEY_ID') or '', 'key_secret': cfg.get('RAZORPAY_KEY_SECRET') or '',
            'webhook_secret': cfg.get('RAZORPAY_WEBHOOK_SECRET') or '', 'source': 'ENV'}


def payment_config():
    cfg = current_app.config
    creds = credentials()
    key_id, secret = creds['key_id'], creds['key_secret']
    configured = bool(key_id and secret)
    mode = 'live' if key_id.startswith('rzp_live_') else 'test'
    settlement = cfg.get('BILL_SETTLEMENT_PROVIDER') or ''
    # Live money must not be collected for a card bill we cannot remit to the issuer.
    live_blocked = configured and mode == 'live' and not settlement
    return {
        'configured': configured and not live_blocked,
        'provider': 'RAZORPAY' if configured else None,
        'mode': mode if configured else None,
        'key_id': key_id if configured else None,     # publishable id — safe for the browser
        'settlement_configured': bool(settlement),
        'message': (
            'Payment integration not configured.' if not configured else
            'Live payments are disabled until a BBPS bill-settlement partner is configured.' if live_blocked else
            'Test mode — no real money moves and the card issuer is not credited.' if mode == 'test' else
            None
        ),
    }


def _auth():
    c = credentials()
    return c['key_id'], c['key_secret']


def _request(method, path, **kwargs):
    url = current_app.config['RAZORPAY_API_BASE'] + path
    try:
        resp = requests.request(method, url, auth=_auth(), timeout=TIMEOUT, **kwargs)
    except requests.RequestException as e:
        logger.error(f'Razorpay {method} {path} network error: {e.__class__.__name__}')
        raise RazorpayError('Payment provider unreachable. Please try again.') from e
    if resp.status_code >= 400:
        try:
            desc = resp.json().get('error', {}).get('description', '')
        except ValueError:
            desc = ''
        logger.error(f'Razorpay {method} {path} -> HTTP {resp.status_code} {desc[:120]}')
        raise RazorpayError('Payment provider rejected the request.')
    return resp.json()


def create_order(amount_paise, receipt, notes):
    return _request('POST', '/orders', json={
        'amount': amount_paise, 'currency': 'INR', 'receipt': receipt, 'notes': notes,
    })


def fetch_payment(payment_id):
    return _request('GET', f'/payments/{payment_id}')


def fetch_order_payments(order_id):
    return _request('GET', f'/orders/{order_id}/payments').get('items', [])


def verify_checkout_signature(order_id, payment_id, signature):
    secret = credentials()['key_secret']
    if not (secret and order_id and payment_id and signature):
        return False
    expected = hmac.new(secret.encode(), f'{order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature))


def verify_webhook_signature(raw_body, signature):
    # Unlike a permissive default, an unconfigured secret REJECTS webhooks.
    secret = credentials()['webhook_secret']
    if not (secret and signature):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature))
