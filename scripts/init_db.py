"""Create the database tables. Run once after starting Postgres:

    docker compose up -d
    uv run python -m scripts.init_db
"""
from app.core import db

if __name__ == "__main__":
    db.init_db()
    print("Tables created (or already existed).")
