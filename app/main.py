"""FastAPI entrypoint — assembly only.

This file wires the app together and nothing else: middleware, the API routes
(see app/api/), and the built frontend. All the actual work lives in
app/services/; the endpoints themselves live in app/api/routes/.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core import db

app = FastAPI(title="Performance Coach")


@app.on_event("startup")
def _ensure_tables() -> None:
    """Create the journal tables on boot so a fresh deploy (e.g. Cloud Run
    pointed at an empty Cloud SQL) works with no manual migration step.
    Best-effort: a transient DB hiccup shouldn't stop the app from serving
    /health. (pgvector's own tables + extension are created lazily on first use.)
    """
    try:
        db.init_db()
    except Exception:
        pass


# Allow the local React dev server (Vite) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Serve the built React frontend (if present) so the whole app lives at one URL.
# Mounted last, at "/", so the API routes above always take precedence; only
# unmatched paths (the SPA and its assets) fall through to the static files.
# Absent in local dev, where the frontend runs on its own Vite server.
if os.path.isdir("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="web")
