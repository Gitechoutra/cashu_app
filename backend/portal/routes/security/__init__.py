import logging

from portal.api import api

ns = api.namespace(
    'security',
    description="App PIN and biometric (WebAuthn) settings"
)

logger = logging.getLogger('cardvault.security')

from .routes import *  # noqa: E402,F401,F403
