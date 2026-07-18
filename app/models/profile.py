"""The long-term profile of one person."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now


class Profile(Base):
    """The long-term, always-current summary of a person, condensed by an LLM
    from their journal and injected into every conversation. Kept to a fixed
    size on purpose — it's sent every turn, so it must not grow without bound.

    Keyed by the person's Firebase uid.
    """

    __tablename__ = "profiles"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[str] = mapped_column(Text, default="")
    # How many journal entries have been folded in, so we can refresh every N.
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
