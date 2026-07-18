"""The shared SQLAlchemy base every model inherits from.

Kept in its own module so each model file can import it without importing the
other models (which would be a circular import).
"""
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    """Current UTC time — the default for every timestamp column."""
    return datetime.now(timezone.utc)
