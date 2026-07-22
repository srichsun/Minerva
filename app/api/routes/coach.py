"""Asking the coach — a read-only path into your own journal."""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUid
from app.schemas.coach import TalkRequest
from app.services import agent

router = APIRouter(tags=["coach"])


@router.post("/agent/stream")
def talk_stream(req: TalkRequest, uid: CurrentUid):
    """Answer a question about the journal, streaming it token by token.

    Requires sign-in. The coach replays today's questions for this user, so
    there is nothing to pass in but the question. The exchange is recorded once
    streaming completes — in the questions table, never the journal.
    """
    return StreamingResponse(
        agent.stream_and_save(req.question, user_id=uid),
        media_type="text/plain",
    )
