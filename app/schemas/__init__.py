"""Pydantic schemas — the API's request/response contract."""
from app.schemas.coach import SpeakRequest, TalkRequest, TalkResponse

# Marks these as deliberate re-exports, so the linter doesn't read them as
# unused imports.
__all__ = ["SpeakRequest", "TalkRequest", "TalkResponse"]
