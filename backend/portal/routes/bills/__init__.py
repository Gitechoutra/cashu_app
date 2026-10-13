import logging

from portal.api import api

ns = api.namespace(
    'bills',
    description="Credit card bills and payments"
)

logger = logging.getLogger('cardvault.bills')

from .routes import *  # noqa: E402,F401,F403
