"""
config/config.py
================
Environment-driven configuration. Every secret comes from the environment
(.env in development, a secret manager in production) — never from source.

APP_ENV selects the class: DEV (default), TEST or PROD.
"""

import os
from datetime import timedelta


def _bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


class BaseConfig:
    APP_NAME = os.getenv('APP_NAME', 'CardVault')
    APP_ENV = 'DEV'
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.getenv('APP_SECRET_KEY', '')
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    BACKEND_PUBLIC_URL = os.getenv('BACKEND_PUBLIC_URL', 'http://localhost:5050').rstrip('/')

    # ── Database ───────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', '')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 1800}

    # ── JWT (short-lived access token; refresh token is an opaque httpOnly cookie) ──
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', '')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_MINUTES', 15)))
    JWT_TOKEN_LOCATION = ['headers']
    JWT_ALGORITHM = 'HS256'

    # ── Sessions / app lock ────────────────────────────────────────────────
    SESSION_ABSOLUTE_DAYS = int(os.getenv('SESSION_ABSOLUTE_DAYS', 30))
    SESSION_IDLE_LOCK_MINUTES = int(os.getenv('SESSION_IDLE_LOCK_MINUTES', 15))
    REFRESH_COOKIE_NAME = 'cv_refresh'
    REFRESH_COOKIE_SECURE = _bool('REFRESH_COOKIE_SECURE', False)
    PIN_MAX_ATTEMPTS = int(os.getenv('PIN_MAX_ATTEMPTS', 5))

    # ── OTP / SMS ──────────────────────────────────────────────────────────
    # SMS_PROVIDER: msg91 | fast2sms | console (console = DEV only, prints to server log)
    SMS_PROVIDER = os.getenv('SMS_PROVIDER', '').strip().lower()
    OTP_LENGTH = 6
    OTP_TTL_SECONDS = int(os.getenv('OTP_TTL_SECONDS', 300))
    OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv('OTP_RESEND_COOLDOWN_SECONDS', 30))
    OTP_MAX_PER_HOUR = int(os.getenv('OTP_MAX_PER_HOUR', 5))                    # unused codes / hour / number
    OTP_ABSOLUTE_MAX_PER_HOUR = int(os.getenv('OTP_ABSOLUTE_MAX_PER_HOUR', 20))  # all codes / hour / number
    OTP_MAX_ATTEMPTS = 5

    # ── WebAuthn (fingerprint / Face ID) ──────────────────────────────────
    WEBAUTHN_RP_ID = os.getenv('WEBAUTHN_RP_ID', 'localhost')
    WEBAUTHN_RP_NAME = os.getenv('WEBAUTHN_RP_NAME', 'CardVault')
    WEBAUTHN_ORIGIN = os.getenv('WEBAUTHN_ORIGIN', 'http://localhost:5173')

    # ── Field encryption (provider tokens) ────────────────────────────────
    DATA_ENCRYPTION_KEY = os.getenv('DATA_ENCRYPTION_KEY', '')

    # ── Rate limiting ─────────────────────────────────────────────────────
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_DEFAULT = os.getenv('RATELIMIT_DEFAULT', '300 per minute')
    RATELIMIT_HEADERS_ENABLED = True

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',') if o.strip()]

    # ── Card data provider (bank linking) ─────────────────────────────────
    # Empty = not configured. See portal/providers/card_data/README.md.
    CARD_DATA_PROVIDER = os.getenv('CARD_DATA_PROVIDER', '').strip().lower()
    CARD_DATA_STALE_HOURS = int(os.getenv('CARD_DATA_STALE_HOURS', 24))
    LINK_SESSION_TTL_MINUTES = int(os.getenv('LINK_SESSION_TTL_MINUTES', 20))

    # ── Payments (Razorpay) ───────────────────────────────────────────────
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
    RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
    RAZORPAY_API_BASE = 'https://api.razorpay.com/v1'
    # Remitting the collected amount to the card issuer needs a BBPS operating
    # unit (BBPOU) partner. Until one is configured, live-mode bill payments are refused.
    BILL_SETTLEMENT_PROVIDER = os.getenv('BILL_SETTLEMENT_PROVIDER', '').strip().lower()
    MAX_CARD_PAYMENT_INR = os.getenv('MAX_CARD_PAYMENT_INR', '500000')


class DevelopmentConfig(BaseConfig):
    APP_ENV = 'DEV'
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', 'mysql+pymysql://root:password@localhost:3306/cardvault'
    )


class TestingConfig(BaseConfig):
    APP_ENV = 'TEST'
    TESTING = True
    SECRET_KEY = 'test-secret'
    JWT_SECRET_KEY = 'test-jwt-secret-that-is-long-enough-for-hs256'
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
    SQLALCHEMY_ENGINE_OPTIONS = {}
    RATELIMIT_ENABLED = False
    SMS_PROVIDER = 'console'
    CARD_DATA_PROVIDER = ''
    RAZORPAY_KEY_ID = 'rzp_test_dummy'
    RAZORPAY_KEY_SECRET = 'test_secret'
    RAZORPAY_WEBHOOK_SECRET = 'test_webhook_secret'
    DATA_ENCRYPTION_KEY = 'mW1eJ7cRk6yQx2Yp0w5S3qQyQ9pM8aV1hB4nD6fG2jA='


class ProductionConfig(BaseConfig):
    APP_ENV = 'PROD'
    REFRESH_COOKIE_SECURE = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_size': int(os.getenv('DB_POOL_SIZE', 10)),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 20)),
    }


CONFIGS = {'DEV': DevelopmentConfig, 'TEST': TestingConfig, 'PROD': ProductionConfig}


def get_config(name=None):
    return CONFIGS.get((name or os.getenv('APP_ENV', 'DEV')).upper(), DevelopmentConfig)


def validate_config(app):
    """Fail fast on missing or unsafe secrets instead of running insecurely."""
    problems = []
    if not app.config.get('SECRET_KEY'):
        problems.append('APP_SECRET_KEY')
    if len(app.config.get('JWT_SECRET_KEY') or '') < 32:
        problems.append('JWT_SECRET_KEY (min 32 chars)')
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        problems.append('DATABASE_URL')
    if app.config['APP_ENV'] == 'PROD':
        if app.config.get('SMS_PROVIDER') in ('', 'console'):
            problems.append('SMS_PROVIDER (console is not allowed in PROD)')
        if not app.config.get('DATA_ENCRYPTION_KEY'):
            problems.append('DATA_ENCRYPTION_KEY')
        if any(o == '*' for o in app.config['CORS_ORIGINS']):
            problems.append('CORS_ORIGINS (wildcard not allowed in PROD)')
    if problems:
        raise RuntimeError('Missing/unsafe configuration: ' + ', '.join(problems))
