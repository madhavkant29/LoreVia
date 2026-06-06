"""Add chapter_kind column to chapters.

Supports front matter (preface, introduction, foreword, prologue, dedication,
toc) and back matter (epilogue, appendix, acknowledgments, afterword, index)
alongside regular chapters. Defaults to 'chapter'.

Revision ID: 20260606_add_chapter_kind
Revises: 20260606_add_public_forum_images
Create Date: 2026-06-06 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260606_add_chapter_kind"
down_revision: str | Sequence[str] | None = "20260606_add_public_forum_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "chapters" in tables:
        columns = {column["name"] for column in inspector.get_columns("chapters")}
        indexes = {index["name"] for index in inspector.get_indexes("chapters")}
        if "chapter_kind" not in columns:
            op.add_column(
                "chapters",
                sa.Column(
                    "chapter_kind",
                    sa.String(),
                    nullable=False,
                    server_default=sa.text("'chapter'::character varying"),
                ),
            )
        if "ix_chapters_chapter_kind" not in indexes:
            op.create_index(
                "ix_chapters_chapter_kind",
                "chapters",
                ["chapter_kind"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "chapters" in tables:
        columns = {column["name"] for column in inspector.get_columns("chapters")}
        indexes = {index["name"] for index in inspector.get_indexes("chapters")}
        if "chapter_kind" in columns:
            if "ix_chapters_chapter_kind" in indexes:
                op.drop_index(
                    "ix_chapters_chapter_kind",
                    table_name="chapters",
                )
            op.drop_column("chapters", "chapter_kind")
