"""Rolling-read tests.

The condense step is an LLM call, so it's mocked — what's checked here is the
wiring: that one person's own days are the raw material, that the previous
reading is carried forward, that the energy ratings go in alongside the
writing, and that nothing rebuilds it unless asked.
"""
from app.services import profile

U = "u-profile"

READING = {
    "who_you_are": "- runs regularly",
    "patterns": "- goes quiet when overloaded",
    "energy": "- mornings are the good hours",
}


def test_no_reading_until_one_is_built(sqlite_db):
    assert profile.get_profile(U) == {}
    assert profile.as_prompt_text(U) == ""


def test_refresh_condenses_and_saves(write_days, monkeypatch):
    write_days(U, "I started running again", "Nervous about the interview")
    seen = {}
    monkeypatch.setattr(
        profile,
        "_condense",
        lambda existing, recent: seen.update(existing=existing, recent=recent)
        or READING,
    )

    assert profile.refresh_profile(U) == READING
    assert profile.get_profile(U) == READING
    # Both days were handed to the condenser as raw material.
    assert "running" in seen["recent"] and "interview" in seen["recent"]
    assert seen["existing"] == {}


def test_the_energy_rating_goes_in_with_the_writing(write_days, monkeypatch):
    """The energy section is read off what they actually rated, not guessed
    from the tone of the writing."""
    write_days(U, "a flat day", energy=3)
    seen = {}
    monkeypatch.setattr(
        profile, "_condense", lambda e, recent: seen.update(recent=recent) or READING
    )

    profile.refresh_profile(U)

    assert "energy 3/10" in seen["recent"]


def test_a_reading_is_built_only_from_that_persons_days(write_days, monkeypatch):
    write_days(U, "only mine")
    write_days("other", "only theirs")
    monkeypatch.setattr(
        profile, "_condense", lambda existing, recent: {"who_you_are": recent}
    )

    profile.refresh_profile(U)

    assert "only mine" in profile.get_profile(U)["who_you_are"]
    assert "only theirs" not in profile.get_profile(U)["who_you_are"]
    assert profile.get_profile("other") == {}


def test_refresh_carries_forward_the_previous_reading(write_days, monkeypatch):
    write_days(U, "first")
    monkeypatch.setattr(profile, "_condense", lambda e, r: {"patterns": "v1"})
    profile.refresh_profile(U)

    captured = {}
    monkeypatch.setattr(
        profile, "_condense", lambda e, r: captured.update(existing=e) or {"patterns": "v2"}
    )
    profile.refresh_profile(U)

    assert captured["existing"] == {"patterns": "v1"}


def test_entries_behind_counts_days_written_since_the_last_rebuild(
    write_days, monkeypatch
):
    write_days(U, "one", "two")
    assert profile.entries_behind(U) == 2

    monkeypatch.setattr(profile, "_condense", lambda e, r: READING)
    profile.refresh_profile(U)
    assert profile.entries_behind(U) == 0

    write_days(U, "three", ending_days_ago=5)
    assert profile.entries_behind(U) == 1


def test_the_prompt_text_keeps_the_sections_in_order(sqlite_db, monkeypatch):
    monkeypatch.setattr(profile, "_condense", lambda e, r: READING)
    profile.refresh_profile(U)

    text = profile.as_prompt_text(U)

    assert text.index("who_you_are") < text.index("patterns") < text.index("energy")
    assert "mornings are the good hours" in text
