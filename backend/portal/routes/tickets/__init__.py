import logging

from portal.api import api

ns = api.namespace(
    'tickets',
    description="Customer help \& support tickets"
)

logger = logging.getLogger('cardvault.tickets')

from .routes import *  # noqa: E402,F401,F403
