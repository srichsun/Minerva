"""Long-term profile tests.

The LLM condense step is mocked, so these run offline and check the wiring:
that we gather one person's recent entries, save the condensed text keyed by
their uid, count what's folded in, and only re-condense once enough new entries
have accumulated.
"""
from app.services import profile

U = "u-profile"


def test_get_profile_empty_when_none(sqlite_db):
    assert profile.get_profile(U) == ""


def test_refresh_condenses_and_saves(write_days, monkeypatch):
    write_days(U, "I started running again", "Nervous about the interview")
    seen = {}
    monkeypatch.setattr(
        profile,
        "_condense",
        lambda existing, recent: seen.update(existing=existing, recent=recent)
        or "- runs regularly\n- job hunting",
    )

    text = profile.refresh_profile(U)

    assert text == "- runs regularly\n- job hunting"
    assert profile.get_profile(U) == "- runs regularly\n- job hunting"
    # Both entries were handed to the condenser as raw material.
    assert "running" in seen["recent"] and "interview" in seen["recent"]
    assert seen["existing"] == ""


def test_profile_is_scoped_per_user(write_days, monkeypatch):
    write_days(U, "only mine")
    write_days("other", "only theirs")
    monkeypatch.setattr(
        profile, "_condense", lambda existing, recent: f"seen:{recent}"
    )

    profile.refresh_profile(U)
    # U's profile is built only from U's entries, not the other account's.
    assert "only mine" in profile.get_profile(U)
    assert "only theirs" not in profile.get_profile(U)
    assert profile.get_profile("other") == ""


def test_refresh_carries_forward_existing_profile(write_days, monkeypatch):
    write_days(U, "first")
    monkeypatch.setattr(profile, "_condense", lambda e, r: "v1")
    profile.refresh_profile(U)

    captured = {}
    monkeypatch.setattr(
        profile, "_condense", lambda e, r: captured.update(existing=e) or "v2"
    )
    profile.refresh_profile(U)
    # The second condense sees the first profile as its starting point.
    assert captured["existing"] == "v1"


def test_maybe_refresh_waits_for_enough_days(write_days, monkeypatch):
    calls = []
    monkeypatch.setattr(profile, "refresh_profile", lambda uid: calls.append(uid))

    # Below the threshold: no refresh.
    write_days(U, *["x"] * (profile.REFRESH_EVERY - 1))
    profile.maybe_refresh(U)
    assert calls == []

    # One more day crosses the threshold: refresh fires.
    write_days(U, "x", ending_days_ago=profile.REFRESH_EVERY - 1)
    profile.maybe_refresh(U)
    assert calls == [U]
