"""Add shared custom tags for revision workflow entities.

Revision ID: 20260514_add_custom_tags
Revises: 20260514_add_beta_read_assignments, 20260514_add_chapter_structure_version, 20260514_add_user_writing_activities
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_custom_tags"
down_revision: tuple[str, ...] | None = (
    "20260514_add_beta_read_assignments",
    "20260514_add_chapter_structure_version",
    "20260514_add_user_writing_activities",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "custom_tags" not in tables:
        op.create_table(
            "custom_tags",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tag_name", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("book_id", "entity_type", "entity_id", "tag_name", name="uq_custom_tags_book_entity_tag"),
        )
        tables.add("custom_tags")

    if "custom_tags" not in tables:
        return

    indexes = _index_names(inspector, "custom_tags")
    for index_name, columns in (
        ("ix_custom_tags_book_id", ["book_id"]),
        ("ix_custom_tags_created_by_user_id", ["created_by_user_id"]),
        ("ix_custom_tags_entity_type", ["entity_type"]),
        ("ix_custom_tags_entity_id", ["entity_id"]),
        ("ix_custom_tags_tag_name", ["tag_name"]),
        ("ix_custom_tags_created_at", ["created_at"]),
        ("ix_custom_tags_book_entity", ["book_id", "entity_type", "entity_id"]),
        ("ix_custom_tags_book_tag_name", ["book_id", "tag_name"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "custom_tags", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "custom_tags" in tables:
        indexes = _index_names(inspector, "custom_tags")
        for index_name in (
            "ix_custom_tags_book_tag_name",
            "ix_custom_tags_book_entity",
            "ix_custom_tags_created_at",
            "ix_custom_tags_tag_name",
            "ix_custom_tags_entity_id",
            "ix_custom_tags_entity_type",
            "ix_custom_tags_created_by_user_id",
            "ix_custom_tags_book_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="custom_tags")
        op.drop_table("custom_tags")
