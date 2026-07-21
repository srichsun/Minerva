"""Rolling user profile — the long-term memory layer ("gets to know you").

The other two memory layers look backward at individual moments: structured SQL
(entries) answers "what happened when", semantic recall (pgvector) finds "a
similar past moment". The profile is different — a short, always-current summary
of who this person *is*: their goals, habits, recurring worries, what triggers
them, what helps. An LLM condenses it from the journal and it's injected into
every conversation, so the coach steadily understands them better without ever
re-reading the whole history.

Fixed size on purpose: injected every turn, so it must not grow without bound.
"""
from app.core import db
from app.services import chat_model, entries
from app.models import Profile

# Re-condense the profile once this many new entries have accumulated. Cheap,
# deterministic, and good enough — we don't need a real-time rewrite every turn.
REFRESH_EVERY = 5

_CONDENSE_PROMPT = (
    "You maintain a rich, evolving profile of a person, built from their "
    "journal. Update the profile below with anything new and lasting from the "
    "recent entries. Keep what is still true, drop one-off trivia. Write it as "
    "bullet points under these headers (omit a header only if there's truly "
    "nothing for it):\n"
    "- **Basic facts**: gender, age, occupation, location — ONLY what they've "
    "actually stated; never guess.\n"
    "- **Goals**\n"
    "- **Strengths**\n"
    "- **Weaknesses / struggles**\n"
    "- **Wins & accomplishments** (notable ones worth remembering)\n"
    "- **Habits & routines**\n"
    "- **Recurring worries**\n"
    "- **Triggers** (what sets them off)\n"
    "- **What helps / what makes them feel good**\n"
    "- **People who matter**\n"
    "- **Preferences** (how they like to be talked to, lifestyle)\n"
    "Be specific and concrete, but stay under ~1000 words — this is injected "
    "into every conversation, so it must not grow without bound.\n\n"
    "Current profile:\n{existing}\n\n"
    "Recent journal entries (newest first):\n{recent}\n\n"
    "Updated profile:"
)


def get_profile(user_id: str) -> str:
    """One person's current profile text, or "" if none has formed yet.

    The profile row is keyed by the person's Firebase uid. No uid (e.g. an
    unauthenticated call) means no profile.
    """
    if not user_id:
        return ""
    with db.get_session() as s:
        row = s.get(Profile, user_id)
        return row.content if row else ""


def condense(existing: str, recent_text: str) -> str:
    """Fold recent entries into the existing profile and return the new text."""
    prompt = _CONDENSE_PROMPT.format(
        existing=existing or "(empty)", recent=recent_text or "(none)"
    )
    return chat_model.build_chat_model().invoke(prompt).content.strip()


def refresh_profile(user_id: str) -> str:
    """Re-condense one person's profile from their latest entries and save it.

    Returns the updated profile text.
    """
    rows = entries.recent_entries(user_id)
    recent_text = "\n".join(f"- {e.transcript}" for e in rows)
    existing = get_profile(user_id)
    updated = condense(existing, recent_text)
    with db.get_session() as s:
        row = s.get(Profile, user_id)
        if row is None:
            row = Profile(key=user_id)
            s.add(row)
        row.content = updated
        row.entry_count = entries.count_entries(user_id)
        s.commit()
    return updated


def maybe_refresh(user_id: str) -> None:
    """Refresh one person's profile only when enough new entries have piled up.

    Called after saving each entry. Cheap no-op most turns; runs the condense
    LLM call about once every REFRESH_EVERY entries.
    """
    with db.get_session() as s:
        row = s.get(Profile, user_id)
        last_count = row.entry_count if row else 0
    if entries.count_entries(user_id) - last_count >= REFRESH_EVERY:
        refresh_profile(user_id)
