"""Add world-building document storage and note linkage.

Revision ID: 20260429_add_world_building_documents
Revises: 20260429_add_world_building_tables
Create Date: 2026-04-29 22:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260429_add_world_building_documents"
down_revision: str | None = "20260429_add_world_building_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "world_building_documents" not in tables:
        op.create_table(
            "world_building_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("source_name", sa.String()),
            sa.Column("s3_key", sa.String(), nullable=False),
            sa.Column("word_count", sa.Integer()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("archived_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_world_building_documents_book_id", "world_building_documents", ["book_id"])
        op.create_index("ix_world_building_documents_is_active", "world_building_documents", ["is_active"])
        op.create_index("ix_world_building_documents_archived_at", "world_building_documents", ["archived_at"])
        op.create_index("ix_world_building_documents_created_at", "world_building_documents", ["created_at"])
        op.create_index("ix_world_building_documents_updated_at", "world_building_documents", ["updated_at"])

    if "world_elements" in tables:
        columns = {column["name"] for column in inspector.get_columns("world_elements")}
        indexes = {index["name"] for index in inspector.get_indexes("world_elements")}
        if "world_document_id" not in columns:
            op.add_column(
                "world_elements",
                sa.Column("world_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("world_building_documents.id", ondelete="CASCADE"), nullable=True),
            )
        if "source_scope" not in columns:
            op.add_column(
                "world_elements",
                sa.Column("source_scope", sa.String(), nullable=True, server_default="story"),
            )
            op.execute(sa.text("UPDATE world_elements SET source_scope = 'story' WHERE source_scope IS NULL"))
            op.alter_column("world_elements", "source_scope", nullable=False, server_default="story")
        if "ix_world_elements_world_document_id" not in indexes:
            op.create_index("ix_world_elements_world_document_id", "world_elements", ["world_document_id"])
        if "ix_world_elements_source_scope" not in indexes:
            op.create_index("ix_world_elements_source_scope", "world_elements", ["source_scope"])

    if "world_notes" in tables:
        columns = {column["name"] for column in inspector.get_columns("world_notes")}
        indexes = {index["name"] for index in inspector.get_indexes("world_notes")}
        if "world_document_id" not in columns:
            op.add_column(
                "world_notes",
                sa.Column("world_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("world_building_documents.id", ondelete="SET NULL"), nullable=True),
            )
        if "context_label" not in columns:
            op.add_column("world_notes", sa.Column("context_label", sa.String(), nullable=True))
        if "suggested_fix" not in columns:
            op.add_column("world_notes", sa.Column("suggested_fix", sa.Text(), nullable=True))
        if "ix_world_notes_world_document_id" not in indexes:
            op.create_index("ix_world_notes_world_document_id", "world_notes", ["world_document_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "world_notes" in tables:
        columns = {column["name"] for column in inspector.get_columns("world_notes")}
        indexes = {index["name"] for index in inspector.get_indexes("world_notes")}
        if "ix_world_notes_world_document_id" in indexes:
            op.drop_index("ix_world_notes_world_document_id", table_name="world_notes")
        if "suggested_fix" in columns:
            op.drop_column("world_notes", "suggested_fix")
        if "context_label" in columns:
            op.drop_column("world_notes", "context_label")
        if "world_document_id" in columns:
            op.drop_column("world_notes", "world_document_id")

    if "world_elements" in tables:
        columns = {column["name"] for column in inspector.get_columns("world_elements")}
        indexes = {index["name"] for index in inspector.get_indexes("world_elements")}
        if "ix_world_elements_source_scope" in indexes:
            op.drop_index("ix_world_elements_source_scope", table_name="world_elements")
        if "ix_world_elements_world_document_id" in indexes:
            op.drop_index("ix_world_elements_world_document_id", table_name="world_elements")
        if "source_scope" in columns:
            op.drop_column("world_elements", "source_scope")
        if "world_document_id" in columns:
            op.drop_column("world_elements", "world_document_id")

    if "world_building_documents" in tables:
        op.drop_table("world_building_documents")
