import logging

from portal.api import api

ns = api.namespace(
    'scan',
    description="Scan and Pay history"
)

logger = logging.getLogger('cardvault.scan')

from .routes import *  # noqa: E402,F401,F403
