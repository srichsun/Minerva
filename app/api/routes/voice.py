"""Voice in (speech-to-text) and out (text-to-speech)."""
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from app.api.deps import CurrentUid
from app.core import config
from app.schemas.coach import SpeakRequest
from app.services import voice

router = APIRouter(tags=["voice"])


@router.post("/transcribe")
async def transcribe(uid: CurrentUid, audio: UploadFile = File(...)):
    """Turn recorded audio into text. The browser then streams the reply via
    /agent/stream, so voice replies type out live like typed ones."""
    data = await audio.read()
    return {"text": voice.transcribe(data, audio.filename or "audio.webm")}


@router.post("/speak")
def speak(req: SpeakRequest, uid: CurrentUid):
    """Turn text into spoken audio (mp3) so the browser can play it.

    Requires sign-in — TTS costs real money per character, so this must not be
    open to the world. If the TTS provider fails (e.g. an out-of-quota plan),
    return 503 with a short reason instead of a raw 500 — the UI skips playback.
    """
    try:
        audio = voice.speak(req.text)
    except Exception as e:
        print(f"TTS failed ({config.TTS_PROVIDER}): {e!r}", flush=True)
        return Response(content=str(e)[:200], media_type="text/plain", status_code=503)
    return Response(content=audio, media_type="audio/mpeg")
