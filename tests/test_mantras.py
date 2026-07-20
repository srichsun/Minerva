"""Tests for the mantras a person keeps.

No LLM anywhere here — the point of a mantra is that it is stored exactly as
written. What matters is that one account can never reach another's lines.
"""
from app.services import mantras


def test_kept_lines_come_back_newest_first(sqlite_db):
    mantras.add_mantra("u1", "Start before you feel ready")
    mantras.add_mantra("u1", "You have done harder things")

    texts = [m.text for m in mantras.list_mantras("u1")]

    assert texts == ["You have done harder things", "Start before you feel ready"]


def test_blank_lines_are_not_kept(sqlite_db):
    assert mantras.add_mantra("u1", "   ") is None
    assert mantras.list_mantras("u1") == []


def test_text_is_stored_exactly_as_written_apart_from_stray_space(sqlite_db):
    kept = mantras.add_mantra("u1", "  today is enough  ")
    assert kept.text == "today is enough"


def test_rewording_replaces_the_text(sqlite_db):
    kept = mantras.add_mantra("u1", "keep going")

    updated = mantras.update_mantra("u1", kept.id, "keep going anyway")

    assert updated.text == "keep going anyway"
    assert [m.text for m in mantras.list_mantras("u1")] == ["keep going anyway"]


def test_deleting_removes_it(sqlite_db):
    kept = mantras.add_mantra("u1", "let it go")

    assert mantras.delete_mantra("u1", kept.id) is True
    assert mantras.list_mantras("u1") == []


# --- one account must never reach another's lines ---

def test_listing_is_scoped_to_one_person(sqlite_db):
    mantras.add_mantra("u1", "mine")
    mantras.add_mantra("u2", "theirs")

    assert [m.text for m in mantras.list_mantras("u1")] == ["mine"]


def test_someone_elses_line_cannot_be_reworded(sqlite_db):
    theirs = mantras.add_mantra("u2", "theirs")

    assert mantras.update_mantra("u1", theirs.id, "hijacked") is None
    assert mantras.list_mantras("u2")[0].text == "theirs"


def test_someone_elses_line_cannot_be_deleted(sqlite_db):
    theirs = mantras.add_mantra("u2", "theirs")

    assert mantras.delete_mantra("u1", theirs.id) is False
    assert len(mantras.list_mantras("u2")) == 1


def test_prompt_text_lists_every_kept_line(sqlite_db):
    mantras.add_mantra("u1", "start small")
    mantras.add_mantra("u1", "today is enough")

    assert mantras.as_prompt_text("u1") == "- today is enough\n- start small"


def test_prompt_text_is_empty_when_nothing_is_kept(sqlite_db):
    assert mantras.as_prompt_text("u1") == ""
