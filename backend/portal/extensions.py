"""
portal/extensions.py
====================
Shared Flask extension instances (the SQLAlchemy `db` lives in portal/__init__.py,
matching the StockVerse layout).
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

migrate = Migrate()

# Defaults and storage come from config (RATELIMIT_DEFAULT / RATELIMIT_STORAGE_URI).
# Use a shared store such as redis:// in production so limits hold across workers.
limiter = Limiter(key_func=get_remote_address)
