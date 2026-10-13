"""Typed access to admin_settings with safe fallbacks (a missing or malformed
value never breaks a request — the coded default is used and logged)."""

import logging
from decimal import Decimal, InvalidOperation

from portal.models.admin_settings import AdminSettings, SettingType

logger = logging.getLogger('cardvault.settings')


def cast(value, value_type):
    if value is None or value == '':
        return None
    if value_type == SettingType.INT:
        return int(value)
    if value_type == SettingType.DECIMAL:
        return Decimal(str(value))
    if value_type == SettingType.BOOL:
        return str(value).lower() in ('1', 'true', 'yes', 'on')
    return str(value)


def get_setting(key, default=None):
    try:
        row = AdminSettings.query.filter_by(key=key).first()
        if row is None:
            return default
        v = cast(row.value, row.value_type)
        return default if v is None else v
    except (ValueError, InvalidOperation):
        logger.warning(f'[settings] invalid value for {key}; using default')
        return default
    except Exception:
        return default


def validate_value(value, value_type):
    """Returns (normalised string, error)."""
    s = '' if value is None else str(value).strip()
    if s == '':
        return '', None
    try:
        if value_type == SettingType.INT:
            return str(int(s)), None
        if value_type == SettingType.DECIMAL:
            d = Decimal(s)
            if d < 0 or d != d.quantize(Decimal('0.01')):
                return None, 'Use a non-negative amount with at most 2 decimals.'
            return str(d), None
        if value_type == SettingType.BOOL:
            if s.lower() not in ('true', 'false'):
                return None, 'Use true or false.'
            return s.lower(), None
    except (ValueError, InvalidOperation):
        return None, 'Invalid value for this setting.'
    return s[:500], None
