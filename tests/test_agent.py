"""Tests for the life-coach agent and the tool helpers.

The coach is driven by a fake, offline chat model, so these tests spend no
tokens and need no API key.
"""
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app.core import clock
from app.services import agent, entries, facts, questions


def _coach_with(replies):
    """Build a coach backed by a fake model that returns the given replies.

    tools=[] because the fake model can't bind tools (the real coach has the
    recall tool); these tests only exercise plain replies and memory.
    """
    fake = GenericFakeChatModel(messages=iter([AIMessage(r) for r in replies]))
    return agent._build_agent(fake, tools=[], middleware=[])


# --- coach agent ---

def test_coach_replies(monkeypatch):
    monkeypatch.setattr(agent, "_agent", _coach_with(["you've got this"]))
    assert agent._reply_to("I feel down today", "u1") == "you've got this"


def test_coach_replays_todays_conversation(sqlite_db, monkeypatch):
    """History comes from the database, not from anything the caller passes in —
    which is what lets a conversation continue on another device or after a
    restart."""
    questions.save("I was nervous", "tell me more", user_id="u1")
    seen = {}
    monkeypatch.setattr(
        agent,
        "_agent",
        type(
            "Spy",
            (),
            {"invoke": lambda self, state, **kw: seen.update(state) or {
                "messages": [AIMessage("ok")]
            }},
        )(),
    )
    agent._reply_to("and then?", user_id="u1")

    assert seen["messages"] == [
        {"role": "user", "content": "I was nervous"},
        {"role": "assistant", "content": "tell me more"},
        {"role": "user", "content": "and then?"},
    ]


def test_history_drops_oldest_when_a_day_runs_long(sqlite_db, monkeypatch):
    """The safety valve trims the oldest exchanges rather than letting the
    request blow past the model's context limit."""
    monkeypatch.setattr(agent, "MAX_HISTORY_CHARS", 100)
    questions.save("x" * 80, "y" * 80, user_id="u1")  # oldest, too big
    questions.save("recent", "reply", user_id="u1")

    history = agent._todays_conversation("u1")

    assert history == [
        {"role": "user", "content": "recent"},
        {"role": "assistant", "content": "reply"},
    ]


def test_history_is_empty_when_it_cannot_be_read(monkeypatch):
    """A database hiccup must never swallow the person's message."""
    monkeypatch.setattr(
        agent.questions,
        "questions_on",
        lambda *a, **k: (_ for _ in ()).throw(OSError()),
    )
    assert agent._todays_conversation("u1") == []


def test_reply_and_save_records_the_question(sqlite_db, monkeypatch):
    monkeypatch.setattr(agent, "_agent", _coach_with(["proud of you"]))

    result = agent.reply_and_save("what have I done lately?", user_id="u1")
    assert result["answer"] == "proud of you"

    saved = questions.questions_on(clock.today(), user_id="u1")
    assert len(saved) == 1
    assert saved[0].question == "what have I done lately?"
    assert saved[0].answer == "proud of you"


def test_asking_never_touches_the_journal(sqlite_db, monkeypatch):
    """The whole point of the split: what the coach knows comes from what the
    person wrote, so asking must add neither an entry nor a fact. Fact
    extraction is left unfaked on purpose — if the read path ever called it,
    the test would try to reach a real model and fail loudly."""
    monkeypatch.setattr(agent, "_agent", _coach_with(["you kept going"]))

    agent.reply_and_save("remind me what I'm good at", user_id="u1")

    assert entries.count_entries("u1") == 0
    assert facts.existing_fact_entry_ids("u1") == set()
