"""Server-side validation — the enforcement boundary. The React rules in
src/app/utils/validation.js mirror these for UX only.

Every validate_* returns (value, error) where error is None when valid."""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MOBILE_IN_RE = re.compile(r'^[6-9]\d{9}$')
OTP_RE = re.compile(r'^\d{6}$')
PIN_RE = re.compile(r'^\d{4,6}$')
LAST4_RE = re.compile(r'^\d{4}$')
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{0,99}$")
NICKNAME_RE = re.compile(r"^[A-Za-z0-9 .,'&()_-]{1,40}$")
BANK_NAME_RE = re.compile(r"^[A-Za-z0-9 .,'&()-]{2,100}$")
IDEMPOTENCY_RE = re.compile(r'^[A-Za-z0-9_-]{16,64}$')

MAX_AMOUNT = Decimal('9999999999.99')
TWO_PLACES = Decimal('0.01')


class Validator:
    """Collects field errors; .response() returns a 400 with all of them."""

    def __init__(self):
        self.errors = {}

    def check(self, field, error):
        if error and field not in self.errors:
            self.errors[field] = error

    @property
    def ok(self):
        return not self.errors

    def response(self):
        from .responses import fail
        return fail(next(iter(self.errors.values())), 400, code='VALIDATION_ERROR', errors=self.errors)


def clean_text(v):
    return re.sub(r'\s+', ' ', str(v)).strip() if v is not None else ''


def normalize_mobile(raw):
    """Accepts 9876543210 / +919876543210 / 919876543210 → '+919876543210'."""
    digits = re.sub(r'[\s-]', '', str(raw or ''))
    if digits.startswith('+91'):
        digits = digits[3:]
    elif len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    if not MOBILE_IN_RE.match(digits):
        return None, 'Enter a valid 10-digit Indian mobile number.'
    return '+91' + digits, None


def validate_otp(v):
    v = str(v or '').strip()
    return (v, None) if OTP_RE.match(v) else (None, 'Enter the 6-digit OTP.')


def validate_pin(v):
    v = str(v or '').strip()
    if not PIN_RE.match(v):
        return None, 'PIN must be 4 to 6 digits.'
    if len(set(v)) == 1 or v in '0123456789' or v in '9876543210':
        return None, 'Choose a less predictable PIN (no repeated or sequential digits).'
    return v, None


def validate_name(v, required=False):
    v = clean_text(v)
    if not v:
        return (None, 'Name is required.') if required else (None, None)
    return (v, None) if NAME_RE.match(v) else (None, 'Use letters, spaces, dots, apostrophes or hyphens only.')


def validate_last4(v):
    v = str(v or '').strip()
    return (v, None) if LAST4_RE.match(v) else (None, 'Enter exactly the last 4 digits of your card.')


def validate_nickname(v):
    v = clean_text(v)
    if not v:
        return None, 'Card nickname is required.'
    return (v, None) if NICKNAME_RE.match(v) else (None, 'Nickname: up to 40 letters, numbers or basic punctuation.')


def validate_bank_name(v):
    v = clean_text(v)
    return (v, None) if BANK_NAME_RE.match(v) else (None, 'Enter a valid bank name.')


def validate_amount(v, label, required=False, allow_zero=True):
    """Parse a rupee amount as Decimal with at most 2 decimal places. Rejects
    floats-as-strings like '1e5', negatives and absurd magnitudes."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return (None, f'{label} is required.') if required else (None, None)
    if isinstance(v, bool):
        return None, f'{label} must be a number.'
    s = str(v).strip().replace(',', '')
    if not re.fullmatch(r'\d+(\.\d+)?', s):
        return None, f'{label} must be a positive amount in rupees.'
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, f'{label} must be a number.'
    if d != d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP):
        return None, f'{label} can have at most 2 decimal places.'
    if d > MAX_AMOUNT:
        return None, f'{label} is too large.'
    if not allow_zero and d == 0:
        return None, f'{label} must be greater than zero.'
    return d.quantize(TWO_PLACES), None


def validate_date(v, label, required=False, past_days=400, future_days=120):
    if v is None or str(v).strip() == '':
        return (None, f'{label} is required.') if required else (None, None)
    try:
        d = datetime.strptime(str(v).strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        return None, f'{label} must be a valid date (YYYY-MM-DD).'
    today = date.today()
    if d < today - timedelta(days=past_days) or d > today + timedelta(days=future_days):
        return None, f'{label} is outside the allowed range.'
    return d, None


def validate_int_range(v, label, lo, hi, required=False):
    if v is None or str(v).strip() == '':
        return (None, f'{label} is required.') if required else (None, None)
    try:
        n = int(str(v).strip())
    except ValueError:
        return None, f'{label} must be a whole number.'
    return (n, None) if lo <= n <= hi else (None, f'{label} must be between {lo} and {hi}.')


def validate_choice(v, choices, label, required=False):
    if v is None or str(v).strip() == '':
        return (None, f'{label} is required.') if required else (None, None)
    v = str(v).strip().upper()
    return (v, None) if v in choices else (None, f'Invalid {label.lower()}.')


def validate_idempotency_key(v):
    v = str(v or '').strip()
    return (v, None) if IDEMPOTENCY_RE.match(v) else (None, 'Invalid request key.')


EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$')


def validate_email(v, required=False):
    v = clean_text(v).lower()
    if not v:
        return (None, 'Email is required.') if required else (None, None)
    return (v[:254], None) if EMAIL_RE.match(v) and len(v) <= 254 else (None, 'Enter a valid email address.')


def validate_staff_pin(v):
    """Staff (Admin / Customer Support) sign in with email + PIN and no OTP,
    so their PIN must be exactly 6 digits and not trivially guessable."""
    v = str(v or '').strip()
    if not re.fullmatch(r'\d{6}', v):
        return None, 'Staff PIN must be exactly 6 digits.'
    return validate_pin(v)
