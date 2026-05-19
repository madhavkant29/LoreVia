"""Add user writing activity history.

Revision ID: 20260514_add_user_writing_activities
Revises: 20260513_add_collaboration_permissions
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_user_writing_activities"
down_revision: str | None = "20260513_add_collaboration_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_writing_activities" not in tables:
        op.create_table(
            "user_writing_activities",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("entry_title", sa.String(), nullable=False),
            sa.Column("words_added", sa.Integer(), nullable=False),
            sa.Column("activity_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("user_writing_activities")

    if "user_writing_activities" not in tables:
        return

    indexes = _index_names(inspector, "user_writing_activities")
    for index_name, columns in (
        ("ix_user_writing_activities_user_id", ["user_id"]),
        ("ix_user_writing_activities_book_id", ["book_id"]),
        ("ix_user_writing_activities_chapter_number", ["chapter_number"]),
        ("ix_user_writing_activities_activity_date", ["activity_date"]),
        ("ix_user_writing_activities_created_at", ["created_at"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "user_writing_activities", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_writing_activities" in tables:
        op.drop_table("user_writing_activities")
