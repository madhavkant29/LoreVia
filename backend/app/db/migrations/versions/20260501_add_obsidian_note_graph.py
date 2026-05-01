"""Add Obsidian note link, tag, backlink, and series-link tables.

Revision ID: 20260501_add_obsidian_note_graph
Revises: 20260430_add_vector_indexes
Create Date: 2026-05-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260501_add_obsidian_note_graph"
down_revision: str | None = "20260430_add_vector_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_indexes(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        index_name
        for index in inspector.get_indexes(table_name)
        if (index_name := index.get("name")) is not None
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "book_obsidian_note_links" not in tables:
        op.create_table(
            "book_obsidian_note_links",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("link_type", sa.String(), nullable=False, server_default="reference"),
            sa.Column("target_label", sa.String()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("source_note_id", "target_note_id", "link_type", name="uq_book_obsidian_note_links_source_target_type"),
        )
        inspector = sa.inspect(bind)
    if "book_obsidian_note_backlinks" not in tables:
        op.create_table(
            "book_obsidian_note_backlinks",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("link_type", sa.String(), nullable=False, server_default="reference"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("source_note_id", "target_note_id", "link_type", name="uq_book_obsidian_note_backlinks_source_target_type"),
        )
        inspector = sa.inspect(bind)
    if "book_obsidian_note_tags" not in tables:
        op.create_table(
            "book_obsidian_note_tags",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tag_name", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("note_id", "tag_name", name="uq_book_obsidian_note_tags_note_tag"),
        )
        inspector = sa.inspect(bind)
    if "book_obsidian_note_series_links" not in tables:
        op.create_table(
            "book_obsidian_note_series_links",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("series_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("link_type", sa.String(), nullable=False, server_default="reference"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("source_note_id", "target_note_id", "link_type", name="uq_book_obsidian_note_series_links_source_target_type"),
        )
        inspector = sa.inspect(bind)

    for table_name, columns in {
        "book_obsidian_note_links": ["user_id", "book_id", "source_note_id", "target_note_id", "link_type", "created_at"],
        "book_obsidian_note_backlinks": ["user_id", "book_id", "source_note_id", "target_note_id", "link_type", "created_at"],
        "book_obsidian_note_tags": ["user_id", "book_id", "note_id", "tag_name", "created_at"],
        "book_obsidian_note_series_links": ["user_id", "series_id", "source_book_id", "target_book_id", "source_note_id", "target_note_id", "link_type", "created_at"],
    }.items():
        if table_name not in tables:
            continue
        indexes = _table_indexes(inspector, table_name)
        for column in columns:
            index_name = f"ix_{table_name}_{column}"
            if index_name not in indexes:
                op.create_index(index_name, table_name, [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name in [
        "book_obsidian_note_series_links",
        "book_obsidian_note_tags",
        "book_obsidian_note_backlinks",
        "book_obsidian_note_links",
    ]:
        if table_name not in tables:
            continue
        indexes = _table_indexes(inspector, table_name)
        for index_name in sorted(indexes):
            if index_name.startswith(f"ix_{table_name}_"):
                op.drop_index(index_name, table_name=table_name)
        op.drop_table(table_name)
