"""Database connection setup (SQLAlchemy).

The engine points at the local Postgres from docker-compose by default.
Tests swap in an in-memory SQLite engine, so they need no running server.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import config
from app.models import Base

engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """Create tables if they don't exist yet."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Open a new database session. Caller closes it (use `with`)."""
    return SessionLocal()
