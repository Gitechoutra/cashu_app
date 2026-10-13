"""
CUSTOMER SUPPORT ACCOUNTS — edit this file to manage Customer Support sign-in credentials.

Staff sign in on their own login page with EMAIL + 6-DIGIT PIN (no OTP).
An agent's credentials are the email and PIN below (mobile number and name are profile details).

How changes apply
-----------------
Save this file. The backend re-runs the seeders on start (and the dev server
restarts by itself when this file is saved), then the database is updated:
  * change `email` / `pin` / `mobile_number` / `full_name` → that account is updated
    (and signed out everywhere if the email, PIN or mobile number changed)
  * add an entry                                  → a new agent is created
  * remove an entry                               → that agent is suspended
Keep each `key` the same for the life of the account — it's how the account
is matched when its email or mobile number changes.

PINs: exactly 6 digits, not repeated or sequential (111111, 123456 are rejected).
The PIN is required (there is no OTP for staff). By default it is read from backend/.env (SUPPORT_PIN) so it isn't
committed to git with this file. You can write it here instead
(e.g. "pin": "593174"), but anyone with repository access will then see it.
"""

import os

from portal.models.roles import RoleName
from .staff_sync import sync_staff

SUPPORT_AGENTS = [
    {
        'key': 'support_agent_1',
        'email': 'ramana123@gmail.com',
        'mobile_number': '9000000002',
        'full_name': 'Customer Support',
        'pin': os.getenv('SUPPORT_PIN', ''),
    },
    # Add more agents like this:
    # {
    #     'key': 'support_agent_2',
    #     'email': 'someone@yourcompany.com',
    #     'mobile_number': '9xxxxxxxxx',
    #     'full_name': 'Second Agent',
    #     'pin': os.getenv('SUPPORT_AGENT_2_PIN', ''),
    # },
]


def seed_customer_support():
    return sync_staff(SUPPORT_AGENTS, RoleName.SUPPORT, 'seed_customersupport.py')
