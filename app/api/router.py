"""Collects every route module into one router that main.py mounts.

Adding a new endpoint group means writing one file under routes/ and adding a
single include_router line here — main.py never has to change.
"""
from fastapi import APIRouter

from app.api.routes import coach, health, journal, profile, voice

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(coach.router)
api_router.include_router(voice.router)
api_router.include_router(journal.router)
api_router.include_router(profile.router)
