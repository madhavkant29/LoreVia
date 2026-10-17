"""Add materialized reader events for cursor-based reader timelines.

Revision ID: 20260912_add_reader_events
Revises: 20260912_social_read_path_indexes
Create Date: 2026-09-12

Reader events are backend-only generated read models. Existing event JSON stays
authoritative during the additive v2 rollout; a bounded worker can materialize
legacy rows without exposing this table through the Supabase Data API.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260912_add_reader_events"
down_revision: str | Sequence[str] | None = "20260912_social_read_path_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "reader_events" not in tables:
        op.create_table(
            "reader_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "generation_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("book_data_generations.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "chapter_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("chapters.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "character_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("characters.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("source_key", sa.String(length=255), nullable=False),
            sa.Column("event_type", sa.String(length=24), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("chapter_title", sa.String(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sort_label", sa.String(), nullable=False),
            sa.Column(
                "payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    inspector = sa.inspect(op.get_bind())
    indexes = _index_names(inspector, "reader_events")
    if "ix_reader_events_book_chapter_sort" not in indexes:
        op.create_index(
            "ix_reader_events_book_chapter_sort",
            "reader_events",
            ["book_id", "chapter_number", "sort_order", "sort_label", "id"],
        )
    if "ix_reader_events_chapter_generation" not in indexes:
        op.create_index(
            "ix_reader_events_chapter_generation",
            "reader_events",
            ["chapter_id", "generation_id"],
        )
    if "uq_reader_events_book_generation_source" not in indexes:
        op.create_index(
            "uq_reader_events_book_generation_source",
            "reader_events",
            ["book_id", "generation_id", "source_key"],
            unique=True,
            postgresql_where=sa.text("generation_id IS NOT NULL"),
        )
    if "uq_reader_events_book_source_unversioned" not in indexes:
        op.create_index(
            "uq_reader_events_book_source_unversioned",
            "reader_events",
            ["book_id", "source_key"],
            unique=True,
            postgresql_where=sa.text("generation_id IS NULL"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "reader_events" not in tables:
        return
    indexes = _index_names(inspector, "reader_events")
    for index_name in (
        "uq_reader_events_book_source_unversioned",
        "uq_reader_events_book_generation_source",
        "ix_reader_events_chapter_generation",
        "ix_reader_events_book_chapter_sort",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="reader_events")
    op.drop_table("reader_events")
