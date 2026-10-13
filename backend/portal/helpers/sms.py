"""
OTP SMS delivery. Same providers as StockVerse (MSG91 primary, Fast2SMS optional).

SMS_PROVIDER:
  msg91    — needs MSG91_AUTH_KEY + MSG91_OTP_TEMPLATE_ID (DLT-approved template)
  fast2sms — needs FAST2SMS_API_KEY
  console  — DEVELOPMENT ONLY: writes the OTP to the backend console so you can
             test without an SMS account. Refused when APP_ENV=PROD.
  (empty)  — not configured: OTP login is unavailable and the API says so.
"""

import os
import logging

import requests
from flask import current_app

logger = logging.getLogger('cardvault.sms')

MSG91_OTP_URL = 'https://api.msg91.com/api/v5/otp'
FAST2SMS_URL = 'https://www.fast2sms.com/dev/bulkV2'


def sms_configured():
    p = current_app.config.get('SMS_PROVIDER')
    if p == 'console':
        return current_app.config['APP_ENV'] != 'PROD'
    if p == 'msg91':
        return bool(os.getenv('MSG91_AUTH_KEY') and os.getenv('MSG91_OTP_TEMPLATE_ID'))
    if p == 'fast2sms':
        return bool(os.getenv('FAST2SMS_API_KEY'))
    return False


def send_otp_sms(e164_mobile, otp):
    """Returns {'success': bool, 'provider': str, 'message': str}. Never logs the
    OTP except in console (dev) mode."""
    provider = current_app.config.get('SMS_PROVIDER')
    if not sms_configured():
        return {'success': False, 'provider': provider or 'none', 'message': 'SMS provider not configured'}

    national = e164_mobile[-10:]
    if provider == 'console':
        # Development convenience only — clearly marked and blocked in PROD.
        current_app.logger.warning(f'[DEV SMS] OTP for {e164_mobile}: {otp}  (console provider — not for production)')
        return {'success': True, 'provider': 'console', 'message': 'OTP written to server console (development)'}
    if provider == 'msg91':
        return _send_via_msg91(national, otp)
    return _send_via_fast2sms(national, otp)


def _send_via_msg91(phone, otp):
    headers = {'authkey': os.getenv('MSG91_AUTH_KEY', ''), 'accept': 'application/json',
               'content-type': 'application/json'}
    payload = {'template_id': os.getenv('MSG91_OTP_TEMPLATE_ID', ''), 'mobile': f'91{phone}',
               'otp': otp, 'otp_length': str(len(otp)), 'otp_expiry': '5'}
    try:
        resp = requests.post(MSG91_OTP_URL, headers=headers, json=payload, timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get('type') == 'success':
            return {'success': True, 'provider': 'msg91', 'message': 'sent'}
        logger.error(f"MSG91 error: {data.get('message', resp.status_code)}")
        return {'success': False, 'provider': 'msg91', 'message': 'SMS delivery failed'}
    except (requests.RequestException, ValueError) as e:
        logger.error(f'MSG91 request failed: {e.__class__.__name__}')
        return {'success': False, 'provider': 'msg91', 'message': 'SMS delivery failed'}


def _send_via_fast2sms(phone, otp):
    headers = {'authorization': os.getenv('FAST2SMS_API_KEY', ''), 'Content-Type': 'application/json'}
    payload = {'variables_values': otp, 'route': 'otp', 'numbers': phone}
    try:
        resp = requests.post(FAST2SMS_URL, headers=headers, json=payload, timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get('return') is True:
            return {'success': True, 'provider': 'fast2sms', 'message': 'sent'}
        logger.error(f'Fast2SMS error: HTTP {resp.status_code}')
        return {'success': False, 'provider': 'fast2sms', 'message': 'SMS delivery failed'}
    except (requests.RequestException, ValueError) as e:
        logger.error(f'Fast2SMS request failed: {e.__class__.__name__}')
        return {'success': False, 'provider': 'fast2sms', 'message': 'SMS delivery failed'}
