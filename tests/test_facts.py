"""Tests for atomic-fact extraction.

The extraction is an LLM call, so it's faked here — these check the glue: that
each fact is written to the facts table with the right date, and each is handed
to the vector index under its category.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core import db
from app.models import Fact
from app.services import facts


class _FakeExtractor:
    """Stands in for the structured-output model, returning canned facts."""

    def __init__(self, result):
        self._result = result
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        return self._result


def _result(*pairs):
    """Build a _FactList from (category, text) pairs."""
    return facts._FactList(
        facts=[facts._Fact(category=c, text=t) for c, t in pairs]
    )


def test_extract_and_save_writes_every_fact_and_indexes_it(sqlite_db, monkeypatch):
    monkeypatch.setattr(
        facts,
        "_extractor",
        _FakeExtractor(
            _result(
                ("health & habits", "went for a run while exhausted"),
                ("work & career", "the project stalled"),
                ("patterns", "keeps going when tired"),
            )
        ),
    )
    indexed = []
    monkeypatch.setattr(
        facts.recall,
        "index_fact",
        lambda fid, text, user_id=None, category=None: indexed.append(
            (fid, text, user_id, category)
        ),
    )

    ids = facts.extract_and_save(7, "tired but ran", "proud of you", user_id="u1")

    assert len(ids) == 3
    # Every fact landed in the table, keyed to the entry and owner.
    rows = facts.existing_fact_entry_ids("u1")
    assert rows == {7}
    # Every fact was handed to the vector index with its category.
    assert [(t, u, c) for (_id, t, u, c) in indexed] == [
        ("went for a run while exhausted", "u1", "health & habits"),
        ("the project stalled", "u1", "work & career"),
        ("keeps going when tired", "u1", "patterns"),
    ]
    assert [fid for (fid, *_rest) in indexed] == ids


def test_extract_and_save_skips_blank_facts(sqlite_db, monkeypatch):
    monkeypatch.setattr(
        facts, "_extractor", _FakeExtractor(_result(("beliefs", "  "), ("beliefs", "x")))
    )
    monkeypatch.setattr(
        facts.recall, "index_fact", lambda *a, **k: None
    )

    ids = facts.extract_and_save(1, "t", "r", user_id="u1")

    assert len(ids) == 1


def _saved_facts(user_id):
    """Every stored fact for one person, oldest first."""
    with db.get_session() as sess:
        return list(sess.scalars(select(Fact).where(Fact.user_id == user_id)))


def test_backfilled_facts_keep_the_entry_s_own_date(sqlite_db, monkeypatch):
    """A fact happened when its exchange did. Backfilling a year of journal in
    one afternoon must not stamp every fact with today."""
    monkeypatch.setattr(facts.recall, "index_fact", lambda *a, **k: None)
    monkeypatch.setattr(
        facts, "_extractor", _FakeExtractor(_result(("health & habits", "ran 5k")))
    )
    back_then = datetime(2026, 3, 4, 9, 30, tzinfo=timezone.utc)

    facts.extract_and_save(1, "a", "b", user_id="u1", created_at=back_then)

    # SQLite drops the tzinfo Postgres would keep, so compare the instant only.
    saved = _saved_facts("u1")[0].created_at
    assert saved.replace(tzinfo=None) == back_then.replace(tzinfo=None)


def test_a_live_exchange_is_stamped_now(sqlite_db, monkeypatch):
    """With no date passed — the live path — the fact is stamped as it lands."""
    monkeypatch.setattr(facts.recall, "index_fact", lambda *a, **k: None)
    monkeypatch.setattr(
        facts, "_extractor", _FakeExtractor(_result(("beliefs", "cold shower")))
    )
    before = datetime.now(timezone.utc).replace(tzinfo=None)

    facts.extract_and_save(1, "a", "b", user_id="u1")

    saved = _saved_facts("u1")[0].created_at
    assert saved.replace(tzinfo=None) >= before
