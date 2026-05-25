"""Add public book ranking snapshots and public update timestamp.

Revision ID: 20260524_add_public_book_rankings
Revises: 20260523_add_character_mentions
Create Date: 2026-05-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260524_add_public_book_rankings"
down_revision: str | Sequence[str] | None = "20260523_add_character_mentions"
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


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for constraint in inspector.get_unique_constraints(table_name)
        if isinstance(name := constraint.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "books" in tables:
        book_columns = _column_names(inspector, "books")
        if "public_updated_at" not in book_columns:
            op.add_column("books", sa.Column("public_updated_at", sa.DateTime(timezone=True), nullable=True))
        inspector = sa.inspect(bind)
        book_indexes = _index_names(inspector, "books")
        if "ix_books_public_updated_at" not in book_indexes:
            op.create_index("ix_books_public_updated_at", "books", ["public_updated_at"])

    if "public_book_rankings" not in tables:
        op.create_table(
            "public_book_rankings",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("surface", sa.String(), nullable=False),
            sa.Column("ranking_key", sa.String(), nullable=False),
            sa.Column("time_window", sa.String(), nullable=False),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("rank_position", sa.Integer(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("primary_timestamp", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "book_id",
                "surface",
                "ranking_key",
                "time_window",
                "snapshot_date",
                name="uq_public_book_rankings_snapshot",
            ),
        )

    inspector = sa.inspect(bind)
    ranking_indexes = _index_names(inspector, "public_book_rankings")
    ranking_unique_constraints = _unique_constraint_names(inspector, "public_book_rankings")

    if "uq_public_book_rankings_snapshot" not in ranking_unique_constraints:
        op.create_unique_constraint(
            "uq_public_book_rankings_snapshot",
            "public_book_rankings",
            ["book_id", "surface", "ranking_key", "time_window", "snapshot_date"],
        )

    for index_name, column_names in (
        (
            "ix_public_book_rankings_surface_key_window_snapshot_rank",
            ["surface", "ranking_key", "time_window", "snapshot_date", "rank_position"],
        ),
        ("ix_public_book_rankings_book_surface", ["book_id", "surface"]),
    ):
        if index_name not in ranking_indexes:
            op.create_index(index_name, "public_book_rankings", column_names)

    op.execute(
        sa.text(
            """
            UPDATE books
            SET public_updated_at = COALESCE(public_updated_at, published_at, created_at)
            WHERE public_updated_at IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "public_book_rankings" in tables:
        ranking_indexes = _index_names(inspector, "public_book_rankings")
        for index_name in (
            "ix_public_book_rankings_book_surface",
            "ix_public_book_rankings_surface_key_window_snapshot_rank",
        ):
            if index_name in ranking_indexes:
                op.drop_index(index_name, table_name="public_book_rankings")
        op.drop_table("public_book_rankings")

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "books" not in tables:
        return

    book_columns = _column_names(inspector, "books")
    book_indexes = _index_names(inspector, "books")
    if "ix_books_public_updated_at" in book_indexes:
        op.drop_index("ix_books_public_updated_at", table_name="books")
    if "public_updated_at" in book_columns:
        op.drop_column("books", "public_updated_at")
