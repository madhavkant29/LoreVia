"""Add approval tracking for author-managed public shares.

Revision ID: 20260516_add_public_share_approval_fields
Revises: 20260516_normalize_unique_constraints
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260516_add_public_share_approval_fields"
down_revision: str | Sequence[str] | None = "20260516_normalize_unique_constraints"
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
    if "books" not in tables:
        return

    columns = _column_names(inspector, "books")
    if "public_share_status" not in columns:
        op.add_column(
            "books",
            sa.Column("public_share_status", sa.String(), nullable=False, server_default="not_requested"),
        )
        inspector = sa.inspect(bind)
        columns = _column_names(inspector, "books")
    if "public_share_requested_at" not in columns:
        op.add_column("books", sa.Column("public_share_requested_at", sa.DateTime(timezone=True), nullable=True))
        inspector = sa.inspect(bind)
        columns = _column_names(inspector, "books")
    if "public_share_approved_at" not in columns:
        op.add_column("books", sa.Column("public_share_approved_at", sa.DateTime(timezone=True), nullable=True))
        inspector = sa.inspect(bind)
        columns = _column_names(inspector, "books")
    if "public_share_approved_by_user_id" not in columns:
        op.add_column(
            "books",
            sa.Column("public_share_approved_by_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        inspector = sa.inspect(bind)

    indexes = _index_names(inspector, "books")
    if "ix_books_public_share_status" not in indexes:
        op.create_index("ix_books_public_share_status", "books", ["public_share_status"])
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "books")
    if "ix_books_public_share_requested_at" not in indexes:
        op.create_index("ix_books_public_share_requested_at", "books", ["public_share_requested_at"])
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "books")
    if "ix_books_public_share_approved_at" not in indexes:
        op.create_index("ix_books_public_share_approved_at", "books", ["public_share_approved_at"])
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "books")
    if "ix_books_public_share_approved_by_user_id" not in indexes:
        op.create_index("ix_books_public_share_approved_by_user_id", "books", ["public_share_approved_by_user_id"])

    op.execute(
        sa.text(
            """
            UPDATE books
            SET public_share_status = CASE
                WHEN is_public = TRUE AND source_kind = 'user_public_share' THEN 'approved'
                ELSE COALESCE(public_share_status, 'not_requested')
            END,
            public_share_requested_at = CASE
                WHEN is_public = TRUE AND source_kind = 'user_public_share' AND public_share_requested_at IS NULL THEN created_at
                ELSE public_share_requested_at
            END,
            public_share_approved_at = CASE
                WHEN is_public = TRUE AND source_kind = 'user_public_share' AND public_share_approved_at IS NULL THEN created_at
                ELSE public_share_approved_at
            END
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "books" not in tables:
        return

    indexes = _index_names(inspector, "books")
    for index_name in (
        "ix_books_public_share_approved_by_user_id",
        "ix_books_public_share_approved_at",
        "ix_books_public_share_requested_at",
        "ix_books_public_share_status",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="books")
            inspector = sa.inspect(bind)
            indexes = _index_names(inspector, "books")

    columns = _column_names(inspector, "books")
    for column_name in (
        "public_share_approved_by_user_id",
        "public_share_approved_at",
        "public_share_requested_at",
        "public_share_status",
    ):
        if column_name in columns:
            op.drop_column("books", column_name)
            inspector = sa.inspect(bind)
            columns = _column_names(inspector, "books")
