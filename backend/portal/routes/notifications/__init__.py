import logging

from portal.api import api

ns = api.namespace(
    'notifications',
    description="In-app notifications"
)

logger = logging.getLogger('cardvault.notifications')

from .routes import *  # noqa: E402,F401,F403
