"""Repair beta read assignment awarded_at drift for existing databases.

Revision ID: 20260518_repair_beta_read_assignment_awarded_at_drift
Revises: 20260518_add_paddle_webhook_events
Create Date: 2026-05-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260518_repair_beta_read_assignment_awarded_at_drift"
down_revision: str | None = "20260518_add_paddle_webhook_events"
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

    if "beta_read_assignments" not in tables:
        return

    columns = _column_names(inspector, "beta_read_assignments")
    if "awarded_at" not in columns:
        op.add_column(
            "beta_read_assignments",
            sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
        )
        columns.add("awarded_at")

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "beta_read_assignments")
    if "awarded_at" in columns and "ix_beta_read_assignments_awarded_at" not in indexes:
        op.create_index(
            "ix_beta_read_assignments_awarded_at",
            "beta_read_assignments",
            ["awarded_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "beta_read_assignments" not in tables:
        return

    indexes = _index_names(inspector, "beta_read_assignments")
    if "ix_beta_read_assignments_awarded_at" in indexes:
        op.drop_index("ix_beta_read_assignments_awarded_at", table_name="beta_read_assignments")

    columns = _column_names(inspector, "beta_read_assignments")
    if "awarded_at" in columns:
        op.drop_column("beta_read_assignments", "awarded_at")
