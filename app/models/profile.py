"""The long-term, rolling read of one person, condensed from their journal."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now


class Profile(Base):
    """What the journal adds up to, in three parts: who this person is, the
    patterns they keep repeating, and what actually lifts their energy.

    Kept as three named sections rather than one blob of prose, because the
    screen shows them as three separate things and the coach leans on them
    differently. Rebuilt only when the person asks for it — nothing here
    updates on its own.

    Keyed by the person's Firebase uid. Bounded on purpose: it is injected into
    every conversation, so it must not grow without end.
    """

    __tablename__ = "profiles"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    # {"who_you_are": ..., "patterns": ..., "energy": ...} — see
    # app.services.profile.SECTIONS.
    sections: Mapped[dict] = mapped_column(JSON, default=dict)
    # How many journal days went into this reading, so the screen can say how
    # far behind it has fallen.
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
