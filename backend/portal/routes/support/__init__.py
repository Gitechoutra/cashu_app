import logging

from portal.api import api

ns = api.namespace(
    'support',
    description="Customer Support: ticket queue and customer lookup"
)

logger = logging.getLogger('cardvault.support')

from .routes import *  # noqa: E402,F401,F403
