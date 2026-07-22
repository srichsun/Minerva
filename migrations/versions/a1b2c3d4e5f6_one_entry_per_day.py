"""one entry per day

Turns `entries` from "one conversation turn" into "one journal day", and adds
the `questions` table that conversation moves to.

The data migration is the interesting part. Existing rows are turns, several
per day, so the unique index cannot go on until they've been folded into one
row per day. Order matters: add the new columns, fold the data, drop the old
columns, then add the index — the index is the last step because it is the
thing that would fail if the fold were wrong.

Old facts are deleted rather than repointed. They were extracted from turns, so
their entry_id refers to rows that no longer exist, and they were filed under
the nine categories that predate `gratitude` — which the record screen shows.
Re-running the extractor over the folded entries is a handful of model calls
and gives facts that match the schema the app now reads.

Revision ID: a1b2c3d4e5f6
Revises: 5527cdb2cde8
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "5527cdb2cde8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Days before this were development testing — dozens of throwaway turns each —
# not journal entries anyone wrote. Folding them would produce two unreadable
# walls of text at the start of the record screen.
KEEP_FROM = "2026-07-17"

# The old product never asked for an energy rating, so the folded days have
# none — and a chart of five empty bars shows nothing at all. These are the
# author rating their own week after the fact, once, for the days that predate
# the question being asked. Nothing else in the app writes energy but the
# person whose day it was.
BACKFILL_ENERGY = {
    "2026-07-17": 7,
    "2026-07-18": 8,
    "2026-07-19": 4,
    "2026-07-20": 9,
    "2026-07-21": 9,
}


def upgrade() -> None:
    op.add_column("entries", sa.Column("entry_date", sa.Date(), nullable=True))
    op.add_column("entries", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("entries", sa.Column("energy", sa.Integer(), nullable=True))
    op.add_column(
        "entries",
        sa.Column("edit_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "entries", sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "entries",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _fold_turns_into_days(bind)

    op.create_index("ix_entries_entry_date", "entries", ["entry_date"])
    op.drop_column("entries", "transcript")
    op.drop_column("entries", "ai_reply")
    op.drop_column("entries", "note")
    for dead in ("mood", "wins", "themes"):
        _drop_if_exists(bind, "entries", dead)

    op.alter_column("entries", "entry_date", nullable=False)
    op.create_unique_constraint(
        "uq_entries_user_day", "entries", ["user_id", "entry_date"]
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("asked_date", sa.Date(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_user_id", "questions", ["user_id"])
    op.create_index("ix_questions_asked_date", "questions", ["asked_date"])
    op.create_index("ix_questions_created_at", "questions", ["created_at"])


def _fold_turns_into_days(bind) -> None:
    """Collapse each person's turns into one row per Taiwan day."""
    # The throwaway development days go first, so nothing below has to work
    # around them.
    bind.execute(
        sa.text(
            "DELETE FROM entries WHERE (created_at AT TIME ZONE 'Asia/Taipei')::date"
            " < :keep_from"
        ),
        {"keep_from": KEEP_FROM},
    )

    # Every surviving turn is stamped with the Taiwan day it belongs to, then
    # the day's transcripts are joined onto its earliest row in the order they
    # were said. The coach's replies are dropped: an entry is what the person
    # wrote, and the replies were answers to a product that no longer exists.
    bind.execute(
        sa.text(
            "UPDATE entries SET entry_date ="
            " (created_at AT TIME ZONE 'Asia/Taipei')::date"
        )
    )
    bind.execute(
        sa.text(
            """
            WITH folded AS (
                SELECT user_id,
                       entry_date,
                       MIN(id) AS keep_id,
                       string_agg(transcript, E'\n\n' ORDER BY created_at) AS content
                FROM entries
                GROUP BY user_id, entry_date
            )
            UPDATE entries e
            SET content = f.content
            FROM folded f
            WHERE e.id = f.keep_id
            """
        )
    )
    bind.execute(sa.text("DELETE FROM entries WHERE content IS NULL"))

    for day, score in BACKFILL_ENERGY.items():
        bind.execute(
            sa.text("UPDATE entries SET energy = :score WHERE entry_date = :day"),
            {"score": score, "day": day},
        )

    # The facts and their embeddings belonged to the turns that just went away.
    bind.execute(sa.text("DELETE FROM facts"))
    bind.execute(sa.text("DELETE FROM langchain_pg_embedding"))


def _drop_if_exists(bind, table: str, column: str) -> None:
    """Drop a column that may already be gone.

    mood/wins/themes were retired from the model long before this migration;
    whether the physical column is still there depends on how old the database
    is, and a fresh one has never had them.
    """
    if bind.dialect.name != "postgresql":
        return
    exists = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns"
            " WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first()
    if exists:
        op.drop_column(table, column)


def downgrade() -> None:
    """One-way. Folding turns into days threw the turns away — the backup at
    ~/Documents/minerva-backups/ is the way back, not this function."""
    raise NotImplementedError("restore from the pg_dump backup instead")
