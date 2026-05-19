"""Optimize public forum read indexes for paged discovery queries.

Revision ID: 20260516_optimize_public_forum_reads
Revises: 20260516_align_schema_with_models
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260516_optimize_public_forum_reads"
down_revision: str | Sequence[str] | None = "20260516_align_schema_with_models"
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

    for table_name, index_name, columns in (
        ("book_forum_posts", "ix_book_forum_posts_status_created_at", ["status", "created_at"]),
        ("book_forum_comments", "ix_book_forum_comments_post_created_at", ["post_id", "created_at"]),
        ("book_forum_interests", "ix_book_forum_interests_post_status_created_at", ["post_id", "status", "created_at"]),
        ("beta_read_assignments", "ix_beta_read_assignments_book_state_rating", ["book_id", "state", "final_rating"]),
    ):
        if table_name not in tables:
            continue
        indexes = _index_names(inspector, table_name)
        if index_name not in indexes:
            op.create_index(index_name, table_name, columns)
            inspector = sa.inspect(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    for table_name, index_name in (
        ("beta_read_assignments", "ix_beta_read_assignments_book_state_rating"),
        ("book_forum_interests", "ix_book_forum_interests_post_status_created_at"),
        ("book_forum_comments", "ix_book_forum_comments_post_created_at"),
        ("book_forum_posts", "ix_book_forum_posts_status_created_at"),
    ):
        if table_name not in tables:
            continue
        indexes = _index_names(inspector, table_name)
        if index_name in indexes:
            op.drop_index(index_name, table_name=table_name)
            inspector = sa.inspect(bind)
