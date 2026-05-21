"""Add character review tables for quarantined candidates and duplicate suggestions.

Revision ID: 20260520_add_character_review_tables
Revises: 20260520_add_public_book_analytics_events
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260520_add_character_review_tables"
down_revision: str | None = "20260520_add_public_book_analytics_events"
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

    if "character_candidates" not in tables:
        op.create_table(
            "character_candidates",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("raw_name", sa.String(), nullable=False),
            sa.Column("proposed_name", sa.String(), nullable=False),
            sa.Column("normalized_name", sa.String(), nullable=False),
            sa.Column("aliases", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("matched_character_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reason_codes", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column(
                "evidence",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("source_batch_key", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["matched_character_id"], ["characters.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_duplicate_suggestions" not in tables:
        op.create_table(
            "character_duplicate_suggestions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("primary_character_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("secondary_character_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reasons", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column(
                "shared_evidence",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["primary_character_id"], ["characters.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["secondary_character_id"], ["characters.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "book_id",
                "primary_character_id",
                "secondary_character_id",
                name="uq_character_duplicate_suggestions_pair",
            ),
        )

    inspector = sa.inspect(bind)
    candidate_indexes = _index_names(inspector, "character_candidates") if "character_candidates" in _table_names(inspector) else set()
    candidate_columns = _column_names(inspector, "character_candidates") if "character_candidates" in _table_names(inspector) else set()
    if "ix_character_candidates_book_status" not in candidate_indexes and candidate_columns:
        op.create_index(
            "ix_character_candidates_book_status",
            "character_candidates",
            ["book_id", "status"],
            unique=False,
        )
    if "ix_character_candidates_book_normalized_name" not in candidate_indexes and candidate_columns:
        op.create_index(
            "ix_character_candidates_book_normalized_name",
            "character_candidates",
            ["book_id", "normalized_name"],
            unique=False,
        )
    if "ix_character_candidates_matched_character_id" not in candidate_indexes and candidate_columns:
        op.create_index(
            "ix_character_candidates_matched_character_id",
            "character_candidates",
            ["matched_character_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    duplicate_indexes = _index_names(inspector, "character_duplicate_suggestions") if "character_duplicate_suggestions" in _table_names(inspector) else set()
    duplicate_columns = _column_names(inspector, "character_duplicate_suggestions") if "character_duplicate_suggestions" in _table_names(inspector) else set()
    duplicate_unique = _unique_constraint_names(inspector, "character_duplicate_suggestions") if "character_duplicate_suggestions" in _table_names(inspector) else set()
    if "ix_character_duplicate_suggestions_book_status" not in duplicate_indexes and duplicate_columns:
        op.create_index(
            "ix_character_duplicate_suggestions_book_status",
            "character_duplicate_suggestions",
            ["book_id", "status"],
            unique=False,
        )
    if "uq_character_duplicate_suggestions_pair" not in duplicate_unique and duplicate_columns:
        op.create_unique_constraint(
            "uq_character_duplicate_suggestions_pair",
            "character_duplicate_suggestions",
            ["book_id", "primary_character_id", "secondary_character_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "character_duplicate_suggestions" in tables:
        duplicate_indexes = _index_names(inspector, "character_duplicate_suggestions")
        if "ix_character_duplicate_suggestions_book_status" in duplicate_indexes:
            op.drop_index("ix_character_duplicate_suggestions_book_status", table_name="character_duplicate_suggestions")
        op.drop_table("character_duplicate_suggestions")

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_candidates" in tables:
        candidate_indexes = _index_names(inspector, "character_candidates")
        if "ix_character_candidates_matched_character_id" in candidate_indexes:
            op.drop_index("ix_character_candidates_matched_character_id", table_name="character_candidates")
        if "ix_character_candidates_book_normalized_name" in candidate_indexes:
            op.drop_index("ix_character_candidates_book_normalized_name", table_name="character_candidates")
        if "ix_character_candidates_book_status" in candidate_indexes:
            op.drop_index("ix_character_candidates_book_status", table_name="character_candidates")
        op.drop_table("character_candidates")
