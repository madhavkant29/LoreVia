"""add manuscript metadata, summary themes, and character growth events

Revision ID: c2d8f1ef4f10
Revises: a3f9b1c7d204
Create Date: 2026-04-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c2d8f1ef4f10"
down_revision = "a3f9b1c7d204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("books", sa.Column("mode", sa.String(), nullable=False, server_default="reader"))
    op.add_column("books", sa.Column("source_kind", sa.String(), nullable=False, server_default="single_upload"))
    op.add_column(
        "characters",
        sa.Column("growth_events", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "character_states",
        sa.Column("growth_event", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "chapter_summaries",
        sa.Column("themes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chapter_summaries", "themes")
    op.drop_column("character_states", "growth_event")
    op.drop_column("characters", "growth_events")
    op.drop_column("books", "source_kind")
    op.drop_column("books", "mode")
