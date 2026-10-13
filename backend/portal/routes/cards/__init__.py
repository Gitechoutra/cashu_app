import logging

from portal.api import api

ns = api.namespace(
    'cards',
    description="Credit cards, bank linking and consents"
)

logger = logging.getLogger('cardvault.cards')

from .routes import *  # noqa: E402,F401,F403
