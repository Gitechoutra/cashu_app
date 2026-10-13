import logging

from portal.api import api

ns = api.namespace(
    'admin',
    description="Administration: users, roles, payments, gateways, banks, audit"
)

logger = logging.getLogger('cardvault.admin')

from .routes import *  # noqa: E402,F401,F403

from .ops import *  # noqa: E402,F401,F403
