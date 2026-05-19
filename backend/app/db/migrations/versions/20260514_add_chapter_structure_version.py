"""Add chapter structure versioning for manuscript scene order.

Revision ID: 20260514_add_chapter_structure_version
Revises: 20260513_add_collaboration_permissions
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260514_add_chapter_structure_version"
down_revision: str | None = "20260513_add_collaboration_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "chapters" in tables:
        chapter_columns = {column["name"] for column in inspector.get_columns("chapters")}
        if "structure_version" not in chapter_columns:
            op.add_column(
                "chapters",
                sa.Column(
                    "structure_version",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )

    if "novel_scenes" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("novel_scenes")}
        if "ix_novel_scenes_book_chapter_sort_order" not in indexes:
            op.create_index(
                "ix_novel_scenes_book_chapter_sort_order",
                "novel_scenes",
                ["book_id", "chapter_number", "sort_order"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "novel_scenes" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("novel_scenes")}
        if "ix_novel_scenes_book_chapter_sort_order" in indexes:
            op.drop_index("ix_novel_scenes_book_chapter_sort_order", table_name="novel_scenes")

    if "chapters" in tables:
        chapter_columns = {column["name"] for column in inspector.get_columns("chapters")}
        if "structure_version" in chapter_columns:
            op.drop_column("chapters", "structure_version")
