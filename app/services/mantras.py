"""The lines someone keeps for their hardest days.

Plain CRUD, deliberately — no LLM anywhere near it. The value of a mantra is
that it is exactly the words the person chose, unchanged, waiting for them
when they can't reach for it themselves.

Every query filters on user_id as well as id. Trusting the id alone would let
anyone read or delete someone else's lines just by guessing a number.
"""
from sqlalchemy import select

from app.core import db
from app.models import Mantra


def list_mantras(user_id: str) -> list[Mantra]:
    """One person's mantras, newest first."""
    if not user_id:
        return []
    with db.get_session() as s:
        stmt = (
            select(Mantra)
            .where(Mantra.user_id == user_id)
            .order_by(Mantra.created_at.desc())
        )
        return list(s.scalars(stmt))


def add_mantra(user_id: str, text: str) -> Mantra | None:
    """Keep a new line. Blank input is ignored rather than stored."""
    text = (text or "").strip()
    if not text:
        return None
    with db.get_session() as s:
        mantra = Mantra(user_id=user_id, text=text)
        s.add(mantra)
        s.commit()
        return mantra


def update_mantra(user_id: str, mantra_id: int, text: str) -> Mantra | None:
    """Reword one of this person's lines. None if the new text is blank, or if
    the line isn't theirs."""
    text = (text or "").strip()
    if not text:
        return None
    with db.get_session() as s:
        mantra = s.scalar(
            select(Mantra).where(Mantra.id == mantra_id, Mantra.user_id == user_id)
        )
        if mantra is None:
            return None
        mantra.text = text
        s.commit()
        return mantra


def delete_mantra(user_id: str, mantra_id: int) -> bool:
    """Remove one of this person's lines. False if it isn't theirs."""
    with db.get_session() as s:
        mantra = s.scalar(
            select(Mantra).where(Mantra.id == mantra_id, Mantra.user_id == user_id)
        )
        if mantra is None:
            return False
        s.delete(mantra)
        s.commit()
        return True


def as_prompt_text(user_id: str) -> str:
    """The mantras as plain lines, for injecting into her prompt."""
    rows = list_mantras(user_id)
    return "\n".join(f"- {m.text}" for m in rows)
