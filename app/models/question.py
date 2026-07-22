"""One question asked of the coach, and its answer.

Deliberately its own table, separate from `entries`. Asking questions must
never grow the journal or the memory built from it: what the coach knows comes
from what the person sat down and wrote, not from what they said in passing.
Keeping the two apart means the read path has nowhere to write even by
accident.

Grouped by `asked_date` (Taiwan time), the same unit as a journal day — so a
conversation ends when the day does instead of running on forever.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, now


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    # The journal day this was asked on, in Taiwan time — the coach replays
    # only today's questions, so tomorrow starts clean.
    asked_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    # Which journal days the answer drew on, as ISO date strings, so the UI can
    # show "from 3/12" under the reply.
    sources: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )
