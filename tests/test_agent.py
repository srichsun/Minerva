"""Tests for the life-coach agent and the tool helpers.

The coach is driven by a fake, offline chat model, so these tests spend no
tokens and need no API key.
"""
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk

from app.core import clock
from app.services import agent, entries, facts, questions


def _coach_with(replies):
    """Build a coach backed by a fake model that returns the given replies.

    tools=[] because the fake model can't bind tools (the real coach has the
    recall tool); these tests only exercise plain replies and memory.
    """
    fake = GenericFakeChatModel(messages=iter([AIMessage(r) for r in replies]))
    return agent._build_agent(fake, tools=[], middleware=[])


def _answer(question, user_id="u1"):
    """Run the streaming path to completion and return the whole answer.

    Streaming is the only way in now, so the tests go through it rather than a
    quieter route kept alive for their benefit.
    """
    return "".join(agent.stream_and_save(question, user_id=user_id))


# --- coach agent ---

def test_coach_replies(sqlite_db, monkeypatch):
    monkeypatch.setattr(agent, "_agent", _coach_with(["you've got this"]))
    assert _answer("I feel down today") == "you've got this"


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
            {"stream": lambda self, state, **kw: seen.update(state)
             or iter([(AIMessageChunk("ok"), {})])},
        )(),
    )
    list(agent.stream_and_save("and then?", user_id="u1"))

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


def test_the_question_and_its_answer_are_recorded(sqlite_db, monkeypatch):
    monkeypatch.setattr(agent, "_agent", _coach_with(["proud of you"]))

    assert _answer("what have I done lately?") == "proud of you"

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

    _answer("remind me what I'm good at")

    assert entries.count_entries("u1") == 0
    assert facts.existing_fact_entry_ids("u1") == set()


def test_the_days_a_question_reached_into_are_recorded(sqlite_db, monkeypatch):
    """Recall stamps every fact with its day, so which days a question touched
    can be read straight off the tool's output — no second model call, and no
    asking her to report on herself."""
    from langchain_core.messages import ToolMessage

    tool_output = ToolMessage(
        content="2026-07-19 — ran 5k\n2026-07-17 — slept badly", tool_call_id="t1"
    )
    monkeypatch.setattr(
        agent,
        "_agent",
        type("Spy", (), {"stream": lambda self, state, **kw: iter([
            (tool_output, {}),
            (AIMessageChunk("here's what I see"), {}),
        ])})(),
    )

    _answer("how's my energy?")

    saved = questions.questions_on(clock.today(), user_id="u1")[0]
    assert saved.sources == ["2026-07-17", "2026-07-19"]
