"""The rolling read of the person, built from their journal."""
from fastapi import APIRouter

from app.services import profile
from app.api.deps import CurrentUid

router = APIRouter(tags=["profile"])


@router.get("/profile")
def read_profile(uid: CurrentUid):
    """The current reading, plus how far behind it has fallen."""
    return {
        "sections": profile.get_profile(uid),
        "entries_behind": profile.entries_behind(uid),
    }


@router.post("/profile/refresh")
def refresh_profile(uid: CurrentUid):
    """Rebuild the reading from the journal. Only ever runs when asked."""
    return {"sections": profile.refresh_profile(uid), "entries_behind": 0}
