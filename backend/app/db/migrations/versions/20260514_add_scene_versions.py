"""Add scene version history for manuscript editing.

Revision ID: 20260514_add_scene_versions
Revises: 1a70eda4d48c
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_scene_versions"
down_revision: str | None = "1a70eda4d48c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "scene_versions" not in tables:
        op.create_table(
            "scene_versions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("scene_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("scene_title", sa.String(), nullable=False),
            sa.Column("scene_description", sa.String(), nullable=True),
            sa.Column("scene_path", sa.String(), nullable=True),
            sa.Column("s3_key", sa.String(), nullable=False),
            sa.Column("word_count", sa.Integer(), nullable=True),
            sa.Column("note", sa.String(), nullable=True),
            sa.Column("snapshot_kind", sa.String(), nullable=False, server_default="manual"),
            sa.Column("restored_from_version_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["scene_id"], ["novel_scenes.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["restored_from_version_id"], ["scene_versions.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("scene_versions")

    if "scene_versions" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("scene_versions")}
    if "scene_description" not in columns:
        op.add_column("scene_versions", sa.Column("scene_description", sa.String(), nullable=True))

    indexes = _index_names(inspector, "scene_versions")
    for index_name, index_columns in (
        ("ix_scene_versions_book_id", ["book_id"]),
        ("ix_scene_versions_scene_id", ["scene_id"]),
        ("ix_scene_versions_chapter_id", ["chapter_id"]),
        ("ix_scene_versions_chapter_number", ["chapter_number"]),
        ("ix_scene_versions_scene_path", ["scene_path"]),
        ("ix_scene_versions_snapshot_kind", ["snapshot_kind"]),
        ("ix_scene_versions_created_at", ["created_at"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "scene_versions", index_columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "scene_versions" not in tables:
        return

    indexes = _index_names(inspector, "scene_versions")
    for index_name in (
        "ix_scene_versions_created_at",
        "ix_scene_versions_snapshot_kind",
        "ix_scene_versions_scene_path",
        "ix_scene_versions_chapter_number",
        "ix_scene_versions_chapter_id",
        "ix_scene_versions_scene_id",
        "ix_scene_versions_book_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="scene_versions")

    op.drop_table("scene_versions")
