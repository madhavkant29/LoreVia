"""Add advisor jobs table and durable user token version.

Revision ID: 20260521_add_advisor_jobs_and_user_token_version
Revises: 20260520_add_public_forum_post_reactions
Create Date: 2026-05-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260521_add_advisor_jobs_and_user_token_version"
down_revision: str | Sequence[str] | None = "20260520_add_public_forum_post_reactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "users" in tables:
        user_columns = _column_names(inspector, "users")
        if "token_version" not in user_columns:
            op.add_column(
                "users",
                sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"),
            )

    if "advisor_jobs" not in tables:
        op.create_table(
            "advisor_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("scope", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="queued"),
            sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if "advisor_jobs" in _table_names(inspector):
        indexes = _index_names(inspector, "advisor_jobs")
        for index_name, columns in (
            ("ix_advisor_jobs_user_id", ["user_id"]),
            ("ix_advisor_jobs_book_id", ["book_id"]),
            ("ix_advisor_jobs_series_id", ["series_id"]),
            ("ix_advisor_jobs_scope", ["scope"]),
            ("ix_advisor_jobs_status", ["status"]),
            ("ix_advisor_jobs_error_code", ["error_code"]),
            ("ix_advisor_jobs_created_at", ["created_at"]),
            ("ix_advisor_jobs_updated_at", ["updated_at"]),
            ("ix_advisor_jobs_expires_at", ["expires_at"]),
        ):
            if index_name not in indexes:
                op.create_index(index_name, "advisor_jobs", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "advisor_jobs" in tables:
        indexes = _index_names(inspector, "advisor_jobs")
        for index_name in (
            "ix_advisor_jobs_expires_at",
            "ix_advisor_jobs_updated_at",
            "ix_advisor_jobs_created_at",
            "ix_advisor_jobs_error_code",
            "ix_advisor_jobs_status",
            "ix_advisor_jobs_scope",
            "ix_advisor_jobs_series_id",
            "ix_advisor_jobs_book_id",
            "ix_advisor_jobs_user_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="advisor_jobs")
        op.drop_table("advisor_jobs")

    inspector = sa.inspect(bind)
    if "users" in _table_names(inspector):
        user_columns = _column_names(inspector, "users")
        if "token_version" in user_columns:
            op.drop_column("users", "token_version")
