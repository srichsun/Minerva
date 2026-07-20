"""A line this person chose to keep.

Everything else in the journal is written *about* them — by them in the moment,
or by an LLM afterwards. This is the one thing they deliberately set down for
their future self to find on a bad day. So it is stored plainly and never
rewritten, summarised, or condensed by anything.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now


class Mantra(Base):
    __tablename__ = "mantras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )
