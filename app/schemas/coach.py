"""Request/response shapes for the coach and voice endpoints.

These are the API contract — what the browser sends and what it gets back.
FastAPI validates incoming JSON against them and documents them at /docs.
Kept separate from the database models: what a caller may send is not the same
thing as what we store.
"""
from pydantic import BaseModel, field_validator


class TalkRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def _must_say_something(cls, v: str) -> str:
        """Reject a blank turn rather than storing an empty journal entry.

        A silent recording or a stray Enter would otherwise cost a model call
        and leave a row with nothing in it. Whitespace is stripped so what gets
        recorded is what was actually asked.
        """
        v = v.strip()
        if not v:
            raise ValueError("say something first")
        return v


class SpeakRequest(BaseModel):
    text: str
