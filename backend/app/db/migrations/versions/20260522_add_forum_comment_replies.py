"""Add reply threading to public forum comments.

Revision ID: 20260522_add_forum_comment_replies
Revises: 20260519_remove_beta_read_awarded_at_residue
Create Date: 2026-05-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260522_add_forum_comment_replies"
down_revision: str | None = "20260519_remove_beta_read_awarded_at_residue"
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


def _foreign_key_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys(table_name)
        if isinstance(foreign_key.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_forum_comments" not in tables:
        return

    columns = _column_names(inspector, "book_forum_comments")
    if "parent_comment_id" not in columns:
        op.add_column("book_forum_comments", sa.Column("parent_comment_id", sa.UUID(), nullable=True))

    inspector = sa.inspect(bind)
    foreign_keys = _foreign_key_names(inspector, "book_forum_comments")
    if "fk_book_forum_comments_parent_comment_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_book_forum_comments_parent_comment_id",
            "book_forum_comments",
            "book_forum_comments",
            ["parent_comment_id"],
            ["id"],
            ondelete="CASCADE",
        )

    indexes = _index_names(inspector, "book_forum_comments")
    if "ix_book_forum_comments_parent_comment_id" not in indexes:
        op.create_index("ix_book_forum_comments_parent_comment_id", "book_forum_comments", ["parent_comment_id"], unique=False)
    if "ix_book_forum_comments_parent_created_at" not in indexes:
        op.create_index(
            "ix_book_forum_comments_parent_created_at",
            "book_forum_comments",
            ["parent_comment_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_forum_comments" not in tables:
        return

    reply_exists = bind.execute(
        sa.text("SELECT id FROM book_forum_comments WHERE parent_comment_id IS NOT NULL LIMIT 1")
    ).fetchone()
    if reply_exists is not None:
        raise RuntimeError("Cannot remove forum comment reply support while reply comments exist.")

    indexes = _index_names(inspector, "book_forum_comments")
    if "ix_book_forum_comments_parent_created_at" in indexes:
        op.drop_index("ix_book_forum_comments_parent_created_at", table_name="book_forum_comments")
    if "ix_book_forum_comments_parent_comment_id" in indexes:
        op.drop_index("ix_book_forum_comments_parent_comment_id", table_name="book_forum_comments")

    foreign_keys = _foreign_key_names(inspector, "book_forum_comments")
    if "fk_book_forum_comments_parent_comment_id" in foreign_keys:
        op.drop_constraint("fk_book_forum_comments_parent_comment_id", "book_forum_comments", type_="foreignkey")

    columns = _column_names(inspector, "book_forum_comments")
    if "parent_comment_id" in columns:
        op.drop_column("book_forum_comments", "parent_comment_id")
