"""Add public forum comment reputation and public profile fields.

Revision ID: 20260514_add_public_forum_reputation_profiles
Revises: 20260514_add_public_beta_forum_and_ratings
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_public_forum_reputation_profiles"
down_revision: str | Sequence[str] | None = "20260514_add_public_beta_forum_and_ratings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "users" in tables:
        user_columns = _column_names(inspector, "users")
        if "reputation_score" not in user_columns:
            op.add_column("users", sa.Column("reputation_score", sa.Integer(), nullable=False, server_default="0"))
        if "reputation_likes_received" not in user_columns:
            op.add_column("users", sa.Column("reputation_likes_received", sa.Integer(), nullable=False, server_default="0"))
        if "reputation_dislikes_received" not in user_columns:
            op.add_column("users", sa.Column("reputation_dislikes_received", sa.Integer(), nullable=False, server_default="0"))

        inspector = sa.inspect(bind)
        user_indexes = _index_names(inspector, "users")
        if "ix_users_reputation_score" not in user_indexes:
            op.create_index("ix_users_reputation_score", "users", ["reputation_score"])

    if "book_forum_comments" not in tables:
        op.create_table(
            "book_forum_comments",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("dislike_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["post_id"], ["book_forum_posts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("book_forum_comments")

    if "book_forum_comment_reactions" not in tables:
        op.create_table(
            "book_forum_comment_reactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("reaction", sa.String(), nullable=False, server_default="like"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["comment_id"], ["book_forum_comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["post_id"], ["book_forum_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("comment_id", "user_id", name="uq_book_forum_comment_reactions_comment_user"),
        )
        tables.add("book_forum_comment_reactions")

    if "book_forum_comments" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "book_forum_comments")
        for index_name, columns in (
            ("ix_book_forum_comments_post_id", ["post_id"]),
            ("ix_book_forum_comments_book_id", ["book_id"]),
            ("ix_book_forum_comments_author_user_id", ["author_user_id"]),
            ("ix_book_forum_comments_created_at", ["created_at"]),
            ("ix_book_forum_comments_updated_at", ["updated_at"]),
        ):
            if index_name not in indexes:
                op.create_index(index_name, "book_forum_comments", columns)

    if "book_forum_comment_reactions" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "book_forum_comment_reactions")
        for index_name, columns in (
            ("ix_book_forum_comment_reactions_comment_id", ["comment_id"]),
            ("ix_book_forum_comment_reactions_post_id", ["post_id"]),
            ("ix_book_forum_comment_reactions_user_id", ["user_id"]),
            ("ix_book_forum_comment_reactions_created_at", ["created_at"]),
            ("ix_book_forum_comment_reactions_updated_at", ["updated_at"]),
        ):
            if index_name not in indexes:
                op.create_index(index_name, "book_forum_comment_reactions", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_forum_comment_reactions" in tables:
        indexes = _index_names(inspector, "book_forum_comment_reactions")
        for index_name in (
            "ix_book_forum_comment_reactions_updated_at",
            "ix_book_forum_comment_reactions_created_at",
            "ix_book_forum_comment_reactions_user_id",
            "ix_book_forum_comment_reactions_post_id",
            "ix_book_forum_comment_reactions_comment_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="book_forum_comment_reactions")
        op.drop_table("book_forum_comment_reactions")

    if "book_forum_comments" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "book_forum_comments")
        for index_name in (
            "ix_book_forum_comments_updated_at",
            "ix_book_forum_comments_created_at",
            "ix_book_forum_comments_author_user_id",
            "ix_book_forum_comments_book_id",
            "ix_book_forum_comments_post_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="book_forum_comments")
        op.drop_table("book_forum_comments")

    if "users" in tables:
        inspector = sa.inspect(bind)
        user_columns = _column_names(inspector, "users")
        user_indexes = _index_names(inspector, "users")
        if "ix_users_reputation_score" in user_indexes:
            op.drop_index("ix_users_reputation_score", table_name="users")
        if "reputation_dislikes_received" in user_columns:
            op.drop_column("users", "reputation_dislikes_received")
        if "reputation_likes_received" in user_columns:
            op.drop_column("users", "reputation_likes_received")
        if "reputation_score" in user_columns:
            op.drop_column("users", "reputation_score")
