"""Add public forum post reactions.

Revision ID: 20260520_add_public_forum_post_reactions
Revises: 20260520_add_character_review_tables
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260520_add_public_forum_post_reactions"
down_revision: str | Sequence[str] | None = "20260520_add_character_review_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name) if index.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_forum_posts" in tables:
        post_columns = _column_names(inspector, "book_forum_posts")
        if "like_count" not in post_columns:
            op.add_column("book_forum_posts", sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"))
        if "dislike_count" not in post_columns:
            op.add_column("book_forum_posts", sa.Column("dislike_count", sa.Integer(), nullable=False, server_default="0"))

    if "book_forum_post_reactions" not in tables:
        op.create_table(
            "book_forum_post_reactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("reaction", sa.String(), nullable=False, server_default="like"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["post_id"], ["book_forum_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id", "user_id", name="uq_book_forum_post_reactions_post_user"),
        )
        tables.add("book_forum_post_reactions")

    inspector = sa.inspect(bind)
    if "book_forum_post_reactions" in _table_names(inspector):
        indexes = _index_names(inspector, "book_forum_post_reactions")
        for index_name, columns in (
            ("ix_book_forum_post_reactions_post_id", ["post_id"]),
            ("ix_book_forum_post_reactions_user_id", ["user_id"]),
            ("ix_book_forum_post_reactions_created_at", ["created_at"]),
            ("ix_book_forum_post_reactions_updated_at", ["updated_at"]),
        ):
            if index_name not in indexes:
                op.create_index(index_name, "book_forum_post_reactions", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_forum_post_reactions" in tables:
        indexes = _index_names(inspector, "book_forum_post_reactions")
        for index_name in (
            "ix_book_forum_post_reactions_updated_at",
            "ix_book_forum_post_reactions_created_at",
            "ix_book_forum_post_reactions_user_id",
            "ix_book_forum_post_reactions_post_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="book_forum_post_reactions")
        op.drop_table("book_forum_post_reactions")

    if "book_forum_posts" in _table_names(sa.inspect(bind)):
        post_columns = _column_names(sa.inspect(bind), "book_forum_posts")
        if "dislike_count" in post_columns:
            op.drop_column("book_forum_posts", "dislike_count")
        if "like_count" in post_columns:
            op.drop_column("book_forum_posts", "like_count")
