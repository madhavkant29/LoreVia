"""Add structured labels to character relationships.

Revision ID: 20260611_complex_relationship_labels
Revises: 20260606_add_chapter_kind
Create Date: 2026-06-11 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260611_complex_relationship_labels"
down_revision: str | Sequence[str] | None = "20260606_add_chapter_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RELATIONSHIP_TABLE = "character_relationships"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if RELATIONSHIP_TABLE not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns(RELATIONSHIP_TABLE)}
    if "shared_labels" not in columns:
        op.add_column(RELATIONSHIP_TABLE, sa.Column("shared_labels", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "character_a_to_b_labels" not in columns:
        op.add_column(RELATIONSHIP_TABLE, sa.Column("character_a_to_b_labels", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "character_b_to_a_labels" not in columns:
        op.add_column(RELATIONSHIP_TABLE, sa.Column("character_b_to_a_labels", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "label_evidence" not in columns:
        op.add_column(RELATIONSHIP_TABLE, sa.Column("label_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if RELATIONSHIP_TABLE not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns(RELATIONSHIP_TABLE)}
    for column_name in (
        "label_evidence",
        "character_b_to_a_labels",
        "character_a_to_b_labels",
        "shared_labels",
    ):
        if column_name in columns:
            op.drop_column(RELATIONSHIP_TABLE, column_name)
