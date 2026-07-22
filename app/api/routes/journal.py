"""Reading back the journal — one day, or a range for the record screen."""
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUid
from app.core import clock
from app.models import Entry
from app.services import entries

router = APIRouter(tags=["journal"])


def _entry_dict(e: Entry) -> dict:
    """Turn a stored Entry into plain JSON for the review screens."""
    return {
        "id": e.id,
        "date": e.entry_date.isoformat(),
        "content": e.content,
        "energy": e.energy,
        "edits_left": max(0, entries.EDIT_LIMIT - e.edit_count),
        "analyzed": e.analyzed_at is not None,
    }


@router.get("/entries")
def entries_in_range(uid: CurrentUid, days: int = 7):
    """The last `days` journal days, oldest first.

    Days with no entry are absent rather than blank — the energy chart draws a
    gap for them, which is the honest picture of a day nobody wrote.
    """
    end = clock.today()
    start = end - timedelta(days=days - 1)
    rows = entries.entries_between(start, end, user_id=uid)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "entries": [_entry_dict(r) for r in rows],
    }


@router.get("/entries/{day}")
def entry_on_day(uid: CurrentUid, day: str):
    """One journal day in full. `day` is YYYY-MM-DD."""
    d = date.fromisoformat(day)
    row = entries.entry_on(d, user_id=uid)
    if row is None:
        raise HTTPException(status_code=404, detail="nothing written that day")
    return _entry_dict(row)
