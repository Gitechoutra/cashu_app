"""
ADMIN ACCOUNTS — edit this file to manage Admin sign-in credentials.

Staff sign in on their own login page with EMAIL + 6-DIGIT PIN (no OTP).
An Admin's credentials are the email and PIN below (mobile number and name are profile details).

How changes apply
-----------------
Save this file. The backend re-runs the seeders on start (and the dev server
restarts by itself when this file is saved), then the database is updated:
  * change `email` / `pin` / `mobile_number` / `full_name` → that account is updated
    (and signed out everywhere if the email, PIN or mobile number changed)
  * add an entry                                  → a new Admin is created
  * remove an entry                               → that Admin is suspended
Keep each `key` the same for the life of the account — it's how the account
is matched when its email or mobile number changes.

PINs: exactly 6 digits, not repeated or sequential (111111, 123456 are rejected).
The PIN is required (there is no OTP for staff). By default it is read from backend/.env (ADMIN_PIN) so it isn't committed
to git with this file. You can write it here instead (e.g. "pin": "482617"),
but anyone with access to the repository will then see it.
"""

import os

from portal.models.roles import RoleName
from .staff_sync import sync_staff

ADMINS = [
    {
        'key': 'primary_admin',
        'email': 'korupolusahithi123@gmail.com',
        'mobile_number': '7287009688',
        'full_name': 'Sahithi',
        'pin': os.getenv('ADMIN_PIN', ''),
    },
    # Add more Admins like this:
    # {
    #     'key': 'second_admin',
    #     'email': 'someone@yourcompany.com',
    #     'mobile_number': '9xxxxxxxxx',
    #     'full_name': 'Second Admin',
    #     'pin': os.getenv('SECOND_ADMIN_PIN', ''),
    # },
]


def seed_admin():
    return sync_staff(ADMINS, RoleName.ADMIN, 'seed_admin.py')
