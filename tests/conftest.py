"""Shared test fixtures."""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import db
from app.models import Base


@pytest.fixture
def sqlite_db(monkeypatch):
    """Point the app's database at a fresh in-memory SQLite for one test.

    One shared connection (StaticPool) so the created tables stick around.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(
        db, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False)
    )
    return engine


@pytest.fixture
def write_days(sqlite_db):
    """Write a run of past journal days for one person, oldest first.

    The app itself can only ever write today — that's the point of it — so a
    test that needs a history has to reach past the service and insert the rows
    directly. Returns the entries, oldest first.
    """

    def _write(
        user_id: str,
        *contents: str,
        energy: int | None = None,
        ending_days_ago: int = 0,
    ):
        from app.core import clock
        from app.models import Entry

        end = clock.today() - timedelta(days=ending_days_ago)
        start = end - timedelta(days=len(contents) - 1)
        rows = [
            Entry(
                user_id=user_id,
                entry_date=start + timedelta(days=i),
                content=text,
                energy=energy,
            )
            for i, text in enumerate(contents)
        ]
        with db.get_session() as s:
            s.add_all(rows)
            s.commit()
        return rows

    return _write
