"""Allow multiple historical public forum posts per book.

Revision ID: 20260517_allow_multiple_public_forum_posts_per_book
Revises: 20260517_remove_monetization_system
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260517_allow_multiple_public_forum_posts_per_book"
down_revision: str | None = "20260517_remove_monetization_system"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE_NAME = "book_forum_posts"
UNIQUE_CONSTRAINT_NAME = "uq_book_forum_posts_book"
BOOK_STATUS_INDEX_NAME = "ix_book_forum_posts_book_status"


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name)
        if isinstance(constraint.get("name"), str)
    }


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        index["name"]
        for index in inspector.get_indexes(table_name)
        if isinstance(index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in _table_names(inspector):
        return

    unique_constraints = _unique_constraint_names(inspector, TABLE_NAME)
    if UNIQUE_CONSTRAINT_NAME in unique_constraints:
        op.drop_constraint(UNIQUE_CONSTRAINT_NAME, TABLE_NAME, type_="unique")

    indexes = _index_names(inspector, TABLE_NAME)
    if BOOK_STATUS_INDEX_NAME not in indexes:
        op.create_index(BOOK_STATUS_INDEX_NAME, TABLE_NAME, ["book_id", "status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in _table_names(inspector):
        return

    indexes = _index_names(inspector, TABLE_NAME)
    if BOOK_STATUS_INDEX_NAME in indexes:
        op.drop_index(BOOK_STATUS_INDEX_NAME, table_name=TABLE_NAME)

    duplicate_books = bind.execute(
        sa.text(
            """
            SELECT book_id
            FROM book_forum_posts
            GROUP BY book_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).fetchone()
    if duplicate_books is not None:
        raise RuntimeError(
            "Cannot restore uq_book_forum_posts_book because one or more books now have multiple forum posts."
        )

    unique_constraints = _unique_constraint_names(inspector, TABLE_NAME)
    if UNIQUE_CONSTRAINT_NAME not in unique_constraints:
        op.create_unique_constraint(UNIQUE_CONSTRAINT_NAME, TABLE_NAME, ["book_id"])
