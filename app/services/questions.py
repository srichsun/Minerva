"""Questions asked of the coach — the read-only side of the app.

This module can write to `questions` and nothing else. It never touches
`entries`, never calls the fact extractor, and never refreshes the profile, so
asking cannot change what the coach knows. That isn't a rule we keep to; the
calls simply don't exist here.
"""
from datetime import date

from sqlalchemy import select

from app.core import clock, db
from app.models import Question


def save(question: str, answer: str, user_id: str, sources: list[str] | None = None) -> int:
    """Store one question and its answer on today's date; return the new id."""
    with db.get_session() as s:
        row = Question(
            user_id=user_id,
            asked_date=clock.today(),
            question=question,
            answer=answer,
            sources=sources or [],
        )
        s.add(row)
        s.commit()
        return row.id


def questions_on(day: date, user_id: str) -> list[Question]:
    """One person's questions from a given day, oldest first."""
    with db.get_session() as s:
        stmt = (
            select(Question)
            .where(Question.user_id == user_id, Question.asked_date == day)
            .order_by(Question.created_at)
        )
        return list(s.scalars(stmt))


def days_with_questions(user_id: str, limit: int = 30) -> list[date]:
    """The days this person asked anything, newest first — the history list."""
    with db.get_session() as s:
        stmt = (
            select(Question.asked_date)
            .where(Question.user_id == user_id)
            .distinct()
            .order_by(Question.asked_date.desc())
            .limit(limit)
        )
        return list(s.scalars(stmt))
