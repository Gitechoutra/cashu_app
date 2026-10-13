"""Default platform settings (Admin -> Platform settings). Idempotent: inserts
missing keys only, never overwrites values an Admin has changed."""

from portal import db
from portal.models.admin_settings import AdminSettings, SettingType

DEFAULTS = [
    # key,                        value,     type,               label,                                    public, description
    ('MIN_CARD_PAYMENT_INR',      '1.00',    SettingType.DECIMAL, 'Minimum bill payment (INR)',            False, 'Smallest amount a customer can pay towards a card bill.'),
    ('MAX_CARD_PAYMENT_INR',      '500000',  SettingType.DECIMAL, 'Maximum bill payment (INR)',            False, 'Largest single card-bill payment.'),
    ('BILL_DUE_REMINDER_DAYS',    '3',       SettingType.INT,     'Due-date reminder (days before)',       False, 'Customers get an in-app reminder this many days before a due date.'),
    ('MAINTENANCE_MESSAGE',       '',        SettingType.STRING,  'Maintenance banner',                    True,  'Shown at the top of the app for everyone when set. Leave empty to hide.'),
    ('SUPPORT_HOURS',             '9 AM - 9 PM, Mon-Sat', SettingType.STRING, 'Support hours',             True,  'Shown on the Help & Support screen.'),
    ('SUPPORT_EMAIL',             '',        SettingType.STRING,  'Support email',                         True,  'Optional contact email shown on Help & Support.'),
]


def seed_admin_settings():
    existing = {k for (k,) in db.session.query(AdminSettings.key).all()}
    added = 0
    for key, value, vtype, label, public, desc in DEFAULTS:
        if key not in existing:
            db.session.add(AdminSettings(key=key, value=value, value_type=vtype, label=label,
                                         is_public=public, description=desc))
            added += 1
    db.session.commit()
    return added
