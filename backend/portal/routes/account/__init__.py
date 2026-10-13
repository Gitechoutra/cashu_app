import logging

from portal.api import api

ns = api.namespace(
    'account',
    description="Profile, security preferences, devices, KYC status, bank accounts"
)

logger = logging.getLogger('cardvault.account')

from .routes import *  # noqa: E402,F401,F403
