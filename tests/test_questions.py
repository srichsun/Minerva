"""Question history tests — the read-only side of the app.

The point of these is less the storage than the separation: asking must leave
the journal untouched.
"""
from datetime import timedelta

from app.core import clock
from app.services import entries, questions

UID = "u1"


def test_save_and_read_back_todays_questions(sqlite_db):
    questions.save("what am I good at?", "quite a lot", UID, sources=["2026-07-18"])
    questions.save("and lately?", "you kept going", UID)

    todays = questions.questions_on(clock.today(), UID)
    assert [q.question for q in todays] == ["what am I good at?", "and lately?"]
    assert todays[0].sources == ["2026-07-18"]


def test_yesterdays_questions_are_not_replayed(sqlite_db):
    questions.save("old question", "old answer", UID)
    yesterday = clock.today() - timedelta(days=1)

    assert questions.questions_on(yesterday, UID) == []


def test_questions_are_scoped_to_one_person(sqlite_db):
    questions.save("mine", "answer", UID)
    questions.save("theirs", "answer", "u2")

    assert [q.question for q in questions.questions_on(clock.today(), UID)] == ["mine"]


def test_asking_does_not_write_a_journal_entry(sqlite_db):
    questions.save("does this journal me?", "no", UID)

    assert entries.count_entries(UID) == 0
    assert entries.today_entry(UID) is None
