"""The lines this person keeps for their hardest days."""
from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUid
from app.models import Mantra
from app.schemas.mantra import MantraRequest
from app.services import mantras

router = APIRouter(prefix="/mantras", tags=["mantras"])


def _dict(m: Mantra) -> dict:
    return {"id": m.id, "text": m.text, "created_at": m.created_at.isoformat()}


@router.get("")
def list_mantras(uid: CurrentUid):
    """Everything this person has kept, newest first."""
    return {"mantras": [_dict(m) for m in mantras.list_mantras(uid)]}


@router.post("")
def add_mantra(req: MantraRequest, uid: CurrentUid):
    """Keep a new line."""
    mantra = mantras.add_mantra(uid, req.text)
    if mantra is None:
        raise HTTPException(status_code=422, detail="A mantra can't be empty")
    return _dict(mantra)


@router.patch("/{mantra_id}")
def update_mantra(mantra_id: int, req: MantraRequest, uid: CurrentUid):
    """Reword one. 404 if it isn't theirs — the same answer as not existing,
    so this can't be used to discover other people's ids."""
    mantra = mantras.update_mantra(uid, mantra_id, req.text)
    if mantra is None:
        raise HTTPException(status_code=404, detail="No such mantra")
    return _dict(mantra)


@router.delete("/{mantra_id}")
def delete_mantra(mantra_id: int, uid: CurrentUid):
    """Let one go."""
    if not mantras.delete_mantra(uid, mantra_id):
        raise HTTPException(status_code=404, detail="No such mantra")
    return {"deleted": mantra_id}
