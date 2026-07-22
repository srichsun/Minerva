"""Extract atomic facts for journal entries that don't have any yet.

Reads every entry, skips the ones that already have facts (so it's safe to
re-run), and runs the fact extraction on the rest. This spends LLM calls — one
per entry — so it prints how many entries it's about to process first.

Run it after the one-entry-per-day migration, which deletes the old facts: they
were extracted from conversation turns that no longer exist.

    docker compose up -d          # needs Postgres + the vector extension
    uv run python -m scripts.backfill_facts
"""
from datetime import datetime, time, timezone

from sqlalchemy import select

from app.core import db
from app.models import Entry
from app.services import facts


def main() -> None:
    with db.get_session() as s:
        all_entries = list(s.scalars(select(Entry).order_by(Entry.entry_date)))

    # Group already-processed entry ids per user so we skip them.
    done_by_user: dict[str, set[int]] = {}
    todo = []
    for e in all_entries:
        done = done_by_user.get(e.user_id)
        if done is None:
            done = facts.existing_fact_entry_ids(e.user_id)
            done_by_user[e.user_id] = done
        if e.id not in done:
            todo.append(e)

    print(f"{len(todo)} ent(r)ies to process (of {len(all_entries)} total).")
    for i, e in enumerate(todo, 1):
        # A fact happened on the day it was written about, not today.
        stamp = datetime.combine(e.entry_date, time.min, tzinfo=timezone.utc)
        try:
            ids = facts.extract_and_save(
                e.id, e.content, e.user_id, created_at=stamp
            )
            print(f"[{i}/{len(todo)}] {e.entry_date}: {len(ids)} facts")
        except Exception as exc:  # keep going; one bad entry shouldn't stop it
            print(f"[{i}/{len(todo)}] {e.entry_date}: FAILED — {exc}")

    print("Done.")


if __name__ == "__main__":
    main()
