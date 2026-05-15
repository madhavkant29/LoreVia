"""Add manuscript annotations.

Revision ID: 20260514_add_manuscript_annotations
Revises: 20260514_add_user_writing_activities
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_manuscript_annotations"
down_revision: str | None = "20260514_add_user_writing_activities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "manuscript_annotations" not in tables:
        op.create_table(
            "manuscript_annotations",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("category", sa.String(), nullable=False, server_default="general"),
            sa.Column("status", sa.String(), nullable=False, server_default="open"),
            sa.Column("visibility", sa.String(), nullable=False, server_default="shared"),
            sa.Column("quote", sa.Text(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("anchor_context_before", sa.Text(), nullable=True),
            sa.Column("anchor_context_after", sa.Text(), nullable=True),
            sa.Column("start_offset", sa.Integer(), nullable=True),
            sa.Column("end_offset", sa.Integer(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("manuscript_annotations")

    if "manuscript_annotations" not in tables:
        return

    indexes = _index_names(inspector, "manuscript_annotations")
    for index_name, columns in (
        ("ix_manuscript_annotations_user_id", ["user_id"]),
        ("ix_manuscript_annotations_book_id", ["book_id"]),
        ("ix_manuscript_annotations_chapter_number", ["chapter_number"]),
        ("ix_manuscript_annotations_category", ["category"]),
        ("ix_manuscript_annotations_status", ["status"]),
        ("ix_manuscript_annotations_visibility", ["visibility"]),
        ("ix_manuscript_annotations_resolved_at", ["resolved_at"]),
        ("ix_manuscript_annotations_created_at", ["created_at"]),
        ("ix_manuscript_annotations_updated_at", ["updated_at"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "manuscript_annotations", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "manuscript_annotations" in tables:
        op.drop_table("manuscript_annotations")
