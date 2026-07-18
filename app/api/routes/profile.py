"""The long-term profile the coach builds up about the person."""
from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.services import profile

router = APIRouter(tags=["profile"])


@router.get("/profile")
def get_profile(uid: CurrentUser):
    """The long-term profile the coach has built up about the person."""
    return {"profile": profile.get_profile(uid)}


@router.post("/profile/refresh")
def refresh_profile(uid: CurrentUser):
    """Force a re-condense of the profile from recent entries (normally this
    happens on its own every few entries)."""
    return {"profile": profile.refresh_profile(uid)}
