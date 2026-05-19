"""Add general public forum thread support.

Revision ID: 20260519_add_general_public_forum_threads
Revises: 20260519_add_public_book_safety_moderation
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260519_add_general_public_forum_threads"
down_revision: str | None = "20260519_add_public_book_safety_moderation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        index["name"]
        for index in inspector.get_indexes(table_name)
        if isinstance(index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_forum_posts" in tables:
        columns = _column_names(inspector, "book_forum_posts")
        if "thread_type" not in columns:
            op.add_column(
                "book_forum_posts",
                sa.Column("thread_type", sa.String(), nullable=True, server_default="novel"),
            )
            op.execute(sa.text("UPDATE book_forum_posts SET thread_type = 'novel' WHERE thread_type IS NULL"))
            op.alter_column("book_forum_posts", "thread_type", nullable=False, server_default="novel")
        if "book_id" in columns:
            op.alter_column("book_forum_posts", "book_id", existing_type=sa.UUID(), nullable=True)
        indexes = _index_names(inspector, "book_forum_posts")
        if "ix_book_forum_posts_thread_type" not in indexes:
            op.create_index("ix_book_forum_posts_thread_type", "book_forum_posts", ["thread_type"], unique=False)
        if "ix_book_forum_posts_thread_type_status_created_at" not in indexes:
            op.create_index(
                "ix_book_forum_posts_thread_type_status_created_at",
                "book_forum_posts",
                ["thread_type", "status", "created_at"],
                unique=False,
            )

    if "book_forum_comments" in tables:
        columns = _column_names(inspector, "book_forum_comments")
        if "book_id" in columns:
            op.alter_column("book_forum_comments", "book_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_forum_comments" in tables:
        general_comment = bind.execute(
            sa.text(
                """
                SELECT c.id
                FROM book_forum_comments AS c
                JOIN book_forum_posts AS p ON p.id = c.post_id
                WHERE p.thread_type = 'general'
                LIMIT 1
                """
            )
        ).fetchone()
        if general_comment is not None:
            raise RuntimeError("Cannot make book_forum_comments.book_id non-null while general forum thread comments exist.")
        columns = _column_names(inspector, "book_forum_comments")
        if "book_id" in columns:
            op.alter_column("book_forum_comments", "book_id", existing_type=sa.UUID(), nullable=False)

    if "book_forum_posts" in tables:
        general_post = bind.execute(sa.text("SELECT id FROM book_forum_posts WHERE thread_type = 'general' LIMIT 1")).fetchone()
        if general_post is not None:
            raise RuntimeError("Cannot remove general public forum support while general forum threads exist.")
        indexes = _index_names(inspector, "book_forum_posts")
        if "ix_book_forum_posts_thread_type_status_created_at" in indexes:
            op.drop_index("ix_book_forum_posts_thread_type_status_created_at", table_name="book_forum_posts")
        if "ix_book_forum_posts_thread_type" in indexes:
            op.drop_index("ix_book_forum_posts_thread_type", table_name="book_forum_posts")
        columns = _column_names(inspector, "book_forum_posts")
        if "book_id" in columns:
            op.alter_column("book_forum_posts", "book_id", existing_type=sa.UUID(), nullable=False)
        if "thread_type" in columns:
            op.drop_column("book_forum_posts", "thread_type")
