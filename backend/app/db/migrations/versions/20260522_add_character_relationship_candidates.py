"""add character relationship review candidates

Revision ID: 20260522_relationship_review
Revises: 20260521_add_advisor_jobs_and_user_token_version
Create Date: 2026-05-22 13:30:00.000000
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260522_relationship_review"
down_revision = "20260521_add_advisor_jobs_and_user_token_version"
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _drop_indexes_if_present(inspector: sa.Inspector, table_name: str, names: Iterable[str]) -> None:
    existing = _index_names(inspector, table_name)
    for name in names:
        if name in existing:
            op.drop_index(name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "character_relationship_candidates" not in tables:
        op.create_table(
            "character_relationship_candidates",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("raw_character_a", sa.String(), nullable=False),
            sa.Column("raw_character_b", sa.String(), nullable=False),
            sa.Column("matched_character_a_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("matched_character_b_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("rel_type", sa.String(), nullable=True),
            sa.Column("sentiment", sa.Float(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("reason_codes", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
            sa.Column("source_batch_key", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["matched_character_a_id"], ["characters.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["matched_character_b_id"], ["characters.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "character_relationship_candidates")
    if "ix_character_relationship_candidates_book_status" not in indexes:
        op.create_index(
            "ix_character_relationship_candidates_book_status",
            "character_relationship_candidates",
            ["book_id", "status"],
        )
    if "ix_character_relationship_candidates_book_chapter" not in indexes:
        op.create_index(
            "ix_character_relationship_candidates_book_chapter",
            "character_relationship_candidates",
            ["book_id", "chapter_number"],
        )
    if "ix_character_relationship_candidates_match_a" not in indexes:
        op.create_index(
            "ix_character_relationship_candidates_match_a",
            "character_relationship_candidates",
            ["matched_character_a_id"],
        )
    if "ix_character_relationship_candidates_match_b" not in indexes:
        op.create_index(
            "ix_character_relationship_candidates_match_b",
            "character_relationship_candidates",
            ["matched_character_b_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_relationship_candidates" not in tables:
        return
    _drop_indexes_if_present(
        inspector,
        "character_relationship_candidates",
        [
            "ix_character_relationship_candidates_book_status",
            "ix_character_relationship_candidates_book_chapter",
            "ix_character_relationship_candidates_match_a",
            "ix_character_relationship_candidates_match_b",
        ],
    )
    op.drop_table("character_relationship_candidates")
