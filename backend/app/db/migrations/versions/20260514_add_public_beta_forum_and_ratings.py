"""Add public beta forum discovery and beta rating fields.

Revision ID: 20260514_add_public_beta_forum_and_ratings
Revises: 20260514_add_beta_read_feedback, 20260514_add_custom_tags, 20260514_add_llm_usage_events, 20260514_add_manual_character_flag, 20260514_add_manuscript_annotations, 20260514_add_scene_versions
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_public_beta_forum_and_ratings"
down_revision: str | Sequence[str] | None = (
    "20260514_add_beta_read_feedback",
    "20260514_add_custom_tags",
    "20260514_add_llm_usage_events",
    "20260514_add_manual_character_flag",
    "20260514_add_manuscript_annotations",
    "20260514_add_scene_versions",
)
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

    if "beta_read_assignments" in tables:
        assignment_columns = _column_names(inspector, "beta_read_assignments")
        if "final_rating" not in assignment_columns:
            op.add_column("beta_read_assignments", sa.Column("final_rating", sa.Float(), nullable=True))

        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "beta_read_assignments")
        if "ix_beta_read_assignments_final_rating" not in indexes:
            op.create_index("ix_beta_read_assignments_final_rating", "beta_read_assignments", ["final_rating"])

    if "book_forum_posts" not in tables:
        op.create_table(
            "book_forum_posts",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("headline", sa.String(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("desired_beta_reader_count", sa.Integer(), nullable=True),
            sa.Column("allow_contact_requests", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("status", sa.String(), nullable=False, server_default="open"),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("book_id", name="uq_book_forum_posts_book"),
        )
        tables.add("book_forum_posts")

    if "book_forum_interests" not in tables:
        op.create_table(
            "book_forum_interests",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("interested_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["interested_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["post_id"], ["book_forum_posts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("post_id", "interested_user_id", name="uq_book_forum_interests_post_user"),
        )
        tables.add("book_forum_interests")

    if "book_forum_posts" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "book_forum_posts")
        for index_name, columns in (
            ("ix_book_forum_posts_book_id", ["book_id"]),
            ("ix_book_forum_posts_author_user_id", ["author_user_id"]),
            ("ix_book_forum_posts_status", ["status"]),
            ("ix_book_forum_posts_last_activity_at", ["last_activity_at"]),
            ("ix_book_forum_posts_created_at", ["created_at"]),
            ("ix_book_forum_posts_updated_at", ["updated_at"]),
        ):
            if index_name not in indexes:
                op.create_index(index_name, "book_forum_posts", columns)

    if "book_forum_interests" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "book_forum_interests")
        for index_name, columns in (
            ("ix_book_forum_interests_post_id", ["post_id"]),
            ("ix_book_forum_interests_book_id", ["book_id"]),
            ("ix_book_forum_interests_author_user_id", ["author_user_id"]),
            ("ix_book_forum_interests_interested_user_id", ["interested_user_id"]),
            ("ix_book_forum_interests_status", ["status"]),
            ("ix_book_forum_interests_responded_at", ["responded_at"]),
            ("ix_book_forum_interests_created_at", ["created_at"]),
            ("ix_book_forum_interests_updated_at", ["updated_at"]),
        ):
            if index_name not in indexes:
                op.create_index(index_name, "book_forum_interests", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_forum_interests" in tables:
        indexes = _index_names(inspector, "book_forum_interests")
        for index_name in (
            "ix_book_forum_interests_updated_at",
            "ix_book_forum_interests_created_at",
            "ix_book_forum_interests_responded_at",
            "ix_book_forum_interests_status",
            "ix_book_forum_interests_interested_user_id",
            "ix_book_forum_interests_author_user_id",
            "ix_book_forum_interests_book_id",
            "ix_book_forum_interests_post_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="book_forum_interests")
        op.drop_table("book_forum_interests")

    if "book_forum_posts" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "book_forum_posts")
        for index_name in (
            "ix_book_forum_posts_updated_at",
            "ix_book_forum_posts_created_at",
            "ix_book_forum_posts_last_activity_at",
            "ix_book_forum_posts_status",
            "ix_book_forum_posts_author_user_id",
            "ix_book_forum_posts_book_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="book_forum_posts")
        op.drop_table("book_forum_posts")

    if "beta_read_assignments" in tables:
        inspector = sa.inspect(bind)
        assignment_columns = _column_names(inspector, "beta_read_assignments")
        indexes = _index_names(inspector, "beta_read_assignments")
        if "ix_beta_read_assignments_final_rating" in indexes:
            op.drop_index("ix_beta_read_assignments_final_rating", table_name="beta_read_assignments")
        if "final_rating" in assignment_columns:
            op.drop_column("beta_read_assignments", "final_rating")
