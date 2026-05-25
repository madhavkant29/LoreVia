"""Add character mention evidence table.

Revision ID: 20260523_add_character_mentions
Revises: 20260523_add_email_preferences
Create Date: 2026-05-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260523_add_character_mentions"
down_revision: str | Sequence[str] | None = "20260523_add_email_preferences"
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

    if "character_mentions" not in tables:
        op.create_table(
            "character_mentions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("raw_name", sa.String(), nullable=False),
            sa.Column("normalized_name", sa.String(), nullable=False),
            sa.Column("source_batch_key", sa.String(), nullable=True),
            sa.Column("cluster_key", sa.String(), nullable=True),
            sa.Column("mention_text", sa.String(), nullable=True),
            sa.Column("matched_character_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resolver_status", sa.String(), nullable=False, server_default="unresolved"),
            sa.Column("resolver_reasons", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column(
                "evidence",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["matched_character_id"], ["characters.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_mentions" not in tables:
        return

    columns = _column_names(inspector, "character_mentions")
    if "cluster_key" not in columns:
        op.add_column("character_mentions", sa.Column("cluster_key", sa.String(), nullable=True))
    if "mention_text" not in columns:
        op.add_column("character_mentions", sa.Column("mention_text", sa.String(), nullable=True))
    if "matched_character_id" not in columns:
        op.add_column("character_mentions", sa.Column("matched_character_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "resolver_status" not in columns:
        op.add_column("character_mentions", sa.Column("resolver_status", sa.String(), nullable=False, server_default="unresolved"))
    if "resolver_reasons" not in columns:
        op.add_column("character_mentions", sa.Column("resolver_reasons", postgresql.ARRAY(sa.String()), nullable=True))

    indexes = _index_names(inspector, "character_mentions")
    for index_name, column_names in (
        ("ix_character_mentions_book_chapter", ["book_id", "chapter_number"]),
        ("ix_character_mentions_book_normalized_name", ["book_id", "normalized_name"]),
        ("ix_character_mentions_book_cluster_key", ["book_id", "cluster_key"]),
        ("ix_character_mentions_matched_character_id", ["matched_character_id"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "character_mentions", column_names, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_mentions" not in tables:
        return

    indexes = _index_names(inspector, "character_mentions")
    for index_name in (
        "ix_character_mentions_matched_character_id",
        "ix_character_mentions_book_cluster_key",
        "ix_character_mentions_book_normalized_name",
        "ix_character_mentions_book_chapter",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="character_mentions")

    op.drop_table("character_mentions")
