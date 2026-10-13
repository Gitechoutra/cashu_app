import logging

from portal.api import api

ns = api.namespace(
    'platform',
    description="Public platform settings"
)

logger = logging.getLogger('cardvault.platform')

from .routes import *  # noqa: E402,F401,F403
