# Container image for the FastAPI backend, built for Cloud Run.
FROM python:3.12-slim

# uv for fast, locked dependency installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install deps first (cached unless the lockfile changes).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Then the application code.
COPY app ./app
COPY scripts ./scripts

# Run uvicorn straight from the venv (no `uv run` re-sync) for fast cold
# starts. Cloud Run sends requests to $PORT (default 8080); shell form expands it.
ENV PORT=8080
CMD .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
