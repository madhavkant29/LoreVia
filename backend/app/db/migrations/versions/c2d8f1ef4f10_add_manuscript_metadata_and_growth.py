"""add manuscript metadata, summary themes, and character growth events

Revision ID: c2d8f1ef4f10
Revises: a3f9b1c7d204
Create Date: 2026-04-20 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c2d8f1ef4f10"
down_revision = "a3f9b1c7d204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "books" in tables:
        book_columns = {column["name"] for column in inspector.get_columns("books")}
        if "mode" not in book_columns:
            op.add_column("books", sa.Column("mode", sa.String(), nullable=False, server_default="reader"))
        if "source_kind" not in book_columns:
            op.add_column("books", sa.Column("source_kind", sa.String(), nullable=False, server_default="single_upload"))
    if "characters" in tables:
        character_columns = {column["name"] for column in inspector.get_columns("characters")}
        if "growth_events" not in character_columns:
            op.add_column(
                "characters",
                sa.Column("growth_events", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'[]'::jsonb")),
            )
    if "character_states" in tables:
        character_state_columns = {column["name"] for column in inspector.get_columns("character_states")}
        if "growth_event" not in character_state_columns:
            op.add_column(
                "character_states",
                sa.Column("growth_event", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            )
    if "chapter_summaries" in tables:
        chapter_summary_columns = {column["name"] for column in inspector.get_columns("chapter_summaries")}
        if "themes" not in chapter_summary_columns:
            op.add_column(
                "chapter_summaries",
                sa.Column("themes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "chapter_summaries" in tables:
        chapter_summary_columns = {column["name"] for column in inspector.get_columns("chapter_summaries")}
        if "themes" in chapter_summary_columns:
            op.drop_column("chapter_summaries", "themes")
    if "character_states" in tables:
        character_state_columns = {column["name"] for column in inspector.get_columns("character_states")}
        if "growth_event" in character_state_columns:
            op.drop_column("character_states", "growth_event")
    if "characters" in tables:
        character_columns = {column["name"] for column in inspector.get_columns("characters")}
        if "growth_events" in character_columns:
            op.drop_column("characters", "growth_events")
    if "books" in tables:
        book_columns = {column["name"] for column in inspector.get_columns("books")}
        if "source_kind" in book_columns:
            op.drop_column("books", "source_kind")
        if "mode" in book_columns:
            op.drop_column("books", "mode")
