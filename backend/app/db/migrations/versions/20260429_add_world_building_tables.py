"""Add world-building tables.

Revision ID: 20260429_add_world_building_tables
Revises: 20260429_rebuild_public_schema
Create Date: 2026-04-29 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260429_add_world_building_tables"
down_revision: str | None = "20260429_rebuild_public_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "world_elements" not in tables:
        op.create_table(
            "world_elements",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("series_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("series.id", ondelete="SET NULL")),
            sa.Column("source_book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="SET NULL")),
            sa.Column("element_type", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("parent_element_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("world_elements.id", ondelete="SET NULL")),
            sa.Column("dependencies", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("gap_score", sa.Float()),
            sa.Column("integration_score", sa.Float()),
            sa.Column("suggestions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("analysis_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("edited_by_author", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("edited_at", sa.DateTime(timezone=True)),
            sa.Column("is_series_canonical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("last_gap_analysis", sa.DateTime(timezone=True)),
            sa.Column("last_integration_analysis", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_world_elements_book_id", "world_elements", ["book_id"])
        op.create_index("ix_world_elements_series_id", "world_elements", ["series_id"])
        op.create_index("ix_world_elements_source_book_id", "world_elements", ["source_book_id"])
        op.create_index("ix_world_elements_element_type", "world_elements", ["element_type"])
        op.create_index("ix_world_elements_name", "world_elements", ["name"])
        op.create_index("ix_world_elements_parent_element_id", "world_elements", ["parent_element_id"])
        op.create_index("ix_world_elements_created_at", "world_elements", ["created_at"])
        op.create_index("ix_world_elements_updated_at", "world_elements", ["updated_at"])

    if "world_gap_analyses" not in tables:
        op.create_table(
            "world_gap_analyses",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE")),
            sa.Column("series_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("series.id", ondelete="CASCADE")),
            sa.Column("analysis_mode", sa.String(), nullable=False),
            sa.Column("gap_categories", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("priority_gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("integration_opportunities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("consistency_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_world_gap_analyses_book_id", "world_gap_analyses", ["book_id"])
        op.create_index("ix_world_gap_analyses_series_id", "world_gap_analyses", ["series_id"])
        op.create_index("ix_world_gap_analyses_analysis_mode", "world_gap_analyses", ["analysis_mode"])
        op.create_index("ix_world_gap_analyses_generated_at", "world_gap_analyses", ["generated_at"])

    if "world_notes" not in tables:
        op.create_table(
            "world_notes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("world_element_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("world_elements.id", ondelete="SET NULL")),
            sa.Column("note_type", sa.String(), nullable=False),
            sa.Column("chapter_number", sa.Integer()),
            sa.Column("title", sa.String()),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("priority", sa.String(), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(), nullable=False, server_default="open"),
            sa.Column("linked_gap_id", sa.String()),
            sa.Column("linked_integration_id", sa.String()),
            sa.Column("addressed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_world_notes_user_id", "world_notes", ["user_id"])
        op.create_index("ix_world_notes_book_id", "world_notes", ["book_id"])
        op.create_index("ix_world_notes_world_element_id", "world_notes", ["world_element_id"])
        op.create_index("ix_world_notes_note_type", "world_notes", ["note_type"])
        op.create_index("ix_world_notes_chapter_number", "world_notes", ["chapter_number"])
        op.create_index("ix_world_notes_priority", "world_notes", ["priority"])
        op.create_index("ix_world_notes_status", "world_notes", ["status"])
        op.create_index("ix_world_notes_created_at", "world_notes", ["created_at"])
        op.create_index("ix_world_notes_updated_at", "world_notes", ["updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "world_notes" in tables:
        op.drop_table("world_notes")
    if "world_gap_analyses" in tables:
        op.drop_table("world_gap_analyses")
    if "world_elements" in tables:
        op.drop_table("world_elements")
