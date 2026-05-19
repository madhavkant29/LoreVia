"""Remove leftover beta read awarded_at residue.

Revision ID: 20260519_remove_beta_read_awarded_at_residue
Revises: 20260519_add_general_public_forum_threads
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260519_remove_beta_read_awarded_at_residue"
down_revision: str | None = "20260519_add_general_public_forum_threads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        index["name"]
        for index in inspector.get_indexes(table_name)
        if isinstance(index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "beta_read_assignments" not in tables:
        return

    indexes = _index_names(inspector, "beta_read_assignments")
    if "ix_beta_read_assignments_awarded_at" in indexes:
        op.drop_index("ix_beta_read_assignments_awarded_at", table_name="beta_read_assignments")
        inspector = sa.inspect(bind)

    columns = _column_names(inspector, "beta_read_assignments")
    if "awarded_at" in columns:
        op.drop_column("beta_read_assignments", "awarded_at")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "beta_read_assignments" not in tables:
        return

    columns = _column_names(inspector, "beta_read_assignments")
    if "awarded_at" not in columns:
        op.add_column("beta_read_assignments", sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True))
        inspector = sa.inspect(bind)

    indexes = _index_names(inspector, "beta_read_assignments")
    if "ix_beta_read_assignments_awarded_at" not in indexes:
        op.create_index("ix_beta_read_assignments_awarded_at", "beta_read_assignments", ["awarded_at"])
