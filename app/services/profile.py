"""The rolling read of one person — the long-term memory layer.

The other two layers look at moments: plain SQL (entries) answers "what
happened on the 18th", semantic recall (pgvector) finds "something like this
before". This one is the sum: who this person is, what they keep doing, and
what actually lifts their energy.

Rebuilt only when the person presses the button. Nothing in the app refreshes
it in the background — the same rule as the day's analysis, and for the same
reason: they should know when the machine has just spent a model call on them,
and be able to read a page without wondering whether it changed underneath.
"""
from pydantic import BaseModel, Field

from app.core import db
from app.models import Profile
from app.services import chat_model, entries

# The three parts of the reading, in the order the screen shows them.
SECTIONS = ("who_you_are", "patterns", "energy")


class Reading(BaseModel):
    """One rolling read of a person, as the model returns it."""

    who_you_are: str = Field(
        description="who this person is, leaning on what they have actually done"
    )
    patterns: str = Field(description="what they keep repeating, good and bad")
    energy: str = Field(description="what raises and drains their energy, and what to do")


_CONDENSE_PROMPT = (
    "You keep a rolling read of one person, built from the journal they write "
    "each day. Rewrite it from the entries below, keeping what is still true "
    "and dropping one-off trivia. Three parts, each a few short paragraphs or "
    "bullets:\n\n"
    "**who_you_are** — who this person is: their situation, what they care "
    "about, the people who matter, what they're reaching for. Ground it in "
    "what they have actually done, and say those things plainly — they lose "
    "sight of their own record, and this is where they come to find it. Never "
    "guess at facts they haven't stated.\n\n"
    "**patterns** — what they keep repeating, especially under stress. Both "
    "kinds: what they reliably do that works, and what they reliably do that "
    "costs them. Be specific and honest; a pattern named vaguely is no use.\n\n"
    "**energy** — read their energy ratings against what they wrote on those "
    "days. What lifts them, what drains them, and one or two concrete things "
    "worth trying. Only what the entries actually support — if the ratings are "
    "too few to say anything, say that instead of inventing a trend.\n\n"
    "Keep the whole thing under ~1000 words: it is injected into every "
    "conversation, so it must not grow without bound.\n\n"
    "Current read:\n{existing}\n\n"
    "Journal entries (newest first):\n{recent}\n\n"
)

_condenser = chat_model.build_chat_model().with_structured_output(Reading)


def get_profile(user_id: str) -> dict:
    """One person's current reading as {section: text}, or {} if none yet."""
    if not user_id:
        return {}
    with db.get_session() as s:
        row = s.get(Profile, user_id)
        return dict(row.sections or {}) if row else {}


def as_prompt_text(user_id: str) -> str:
    """The reading flattened into prose, for injecting into the coach's prompt."""
    sections = get_profile(user_id)
    parts = [f"{name}:\n{sections[name]}" for name in SECTIONS if sections.get(name)]
    return "\n\n".join(parts)


def entries_behind(user_id: str) -> int:
    """How many journal days have been written since the last rebuild.

    The screen shows this so the button isn't a mystery: pressing it is worth
    something when this is more than zero, and nothing when it isn't.
    """
    with db.get_session() as s:
        row = s.get(Profile, user_id)
        last = row.entry_count if row else 0
    return max(0, entries.count_entries(user_id) - last)


def _condense(existing: dict, recent_text: str) -> dict:
    """Fold recent entries into the existing reading and return the new one."""
    existing_text = "\n\n".join(
        f"{name}:\n{existing[name]}" for name in SECTIONS if existing.get(name)
    )
    result = _condenser.invoke(
        _CONDENSE_PROMPT.format(
            existing=existing_text or "(empty)", recent=recent_text or "(none)"
        )
    )
    return result.model_dump()


def refresh_profile(user_id: str) -> dict:
    """Rebuild one person's reading from their journal and save it.

    The energy rating goes in alongside the writing, so the energy section is
    read off what they actually rated rather than guessed from the tone.
    """
    rows = entries.recent_entries(user_id)
    recent_text = "\n\n".join(
        f"[{e.entry_date} · energy {e.energy if e.energy else '—'}/10]\n{e.content}"
        for e in rows
    )
    updated = _condense(get_profile(user_id), recent_text)
    with db.get_session() as s:
        row = s.get(Profile, user_id)
        if row is None:
            row = Profile(key=user_id)
            s.add(row)
        row.sections = updated
        row.entry_count = entries.count_entries(user_id)
        s.commit()
    return updated
