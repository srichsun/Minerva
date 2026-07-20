"""Request shapes for keeping and rewording mantras."""
from pydantic import BaseModel


class MantraRequest(BaseModel):
    text: str
