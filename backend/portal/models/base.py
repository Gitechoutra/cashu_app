import secrets
from datetime import datetime, timezone

from portal import db


def utcnow():
    """Naive UTC timestamp (MySQL DATETIME has no timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_public_id():
    """Unguessable identifier exposed in URLs instead of auto-increment keys."""
    return secrets.token_hex(16)


def iso(dt):
    """Serialise a naive-UTC datetime as ISO-8601 with an explicit Z."""
    return dt.isoformat(timespec='seconds') + 'Z' if dt else None


class CrudMixin:
    def save(self):
        db.session.add(self)
        db.session.commit()

    def update(self):
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()
