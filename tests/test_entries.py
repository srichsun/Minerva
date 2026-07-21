"""Journal entry storage tests, run against an in-memory SQLite database
so they need no Postgres server and spend no time on I/O.

The sqlite_db fixture lives in conftest.py."""
from datetime import datetime, timezone

from app.services import entries

UID = "u1"


def test_save_and_read_back(sqlite_db):
    new_id = entries.save_entry(
        "I ran 5k today", "That's a real win!", UID, mood="proud", wins="ran 5k"
    )
    assert isinstance(new_id, int)

    todays = entries.entries_on(datetime.now(timezone.utc).date(), UID)
    assert len(todays) == 1
    assert todays[0].transcript == "I ran 5k today"
    assert todays[0].mood == "proud"


def test_recent_wins_only_returns_entries_with_wins(sqlite_db):
    entries.save_entry("nothing much happened", "that's okay", UID, wins=None)
    entries.save_entry("finished the report", "great job", UID, wins="finished report")

    wins = entries.recent_wins(UID)
    assert len(wins) == 1
    assert wins[0].wins == "finished report"


def test_entries_are_scoped_to_one_person(sqlite_db):
    entries.save_entry("mine", "reply", UID, wins="mine")
    entries.save_entry("theirs", "reply", "u2", wins="theirs")

    assert [e.wins for e in entries.recent_wins(UID)] == ["mine"]
    assert [e.wins for e in entries.recent_wins("u2")] == ["theirs"]
