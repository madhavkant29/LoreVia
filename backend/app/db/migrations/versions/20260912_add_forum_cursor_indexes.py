"""Add stable cursor-order indexes for secondary forum collections.

Revision ID: 20260912_add_forum_cursor_indexes
Revises: 20260912_add_world_analysis_snapshots
Create Date: 2026-09-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260912_add_forum_cursor_indexes"
down_revision: str | Sequence[str] | None = "20260912_add_world_analysis_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES: tuple[tuple[str, str, str], ...] = (
    (
        "book_forum_posts",
        "ix_book_forum_posts_author_updated_id",
        "author_user_id, updated_at, id",
    ),
    (
        "book_forum_interests",
        "ix_book_forum_interests_post_created_id",
        "post_id, created_at, id",
    ),
    (
        "book_forum_comments",
        "ix_book_forum_comments_post_created_id",
        "post_id, created_at, id",
    ),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table_name, index_name, columns in INDEXES:
        if table_name not in tables:
            continue
        existing = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name in existing:
            continue
        with op.get_context().autocommit_block():
            op.execute(
                sa.text(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                    f"ON {table_name} ({columns})"
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table_name, index_name, _columns in reversed(INDEXES):
        if table_name not in tables:
            continue
        existing = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name not in existing:
            continue
        with op.get_context().autocommit_block():
            op.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}"))
