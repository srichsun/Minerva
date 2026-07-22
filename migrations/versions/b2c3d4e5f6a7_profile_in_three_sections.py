"""profile in three sections

The rolling read becomes three named sections instead of one blob of prose,
because the screen shows them as three separate things.

The old `content` is dropped rather than parsed into sections. It was written
by a prompt that asked for eleven different headers, so there is no reliable
way to split it into these three — and it is rebuilt from the journal by one
model call the moment anyone presses the button. Parsing it would be work spent
on data with a shelf life of one click.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("sections", sa.JSON(), nullable=True))
    op.drop_column("profiles", "content")
    # Nothing has been folded into the new sections yet, so the screen should
    # say the whole journal is waiting rather than claim it is up to date.
    op.execute("UPDATE profiles SET entry_count = 0")


def downgrade() -> None:
    op.add_column("profiles", sa.Column("content", sa.Text(), nullable=True))
    op.drop_column("profiles", "sections")
