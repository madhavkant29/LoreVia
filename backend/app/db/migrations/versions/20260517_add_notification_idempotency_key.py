"""Add durable idempotency keys to notifications for retry-safe jobs.

Revision ID: 20260517_add_notification_idempotency_key
Revises: 20260517_drop_redundant_subscription_event_index
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260517_add_notification_idempotency_key"
down_revision: str | None = "20260517_drop_redundant_subscription_event_index"
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


def _duplicate_non_null_idempotency_keys(bind: sa.Connection) -> list[str]:
    rows = bind.execute(
        sa.text(
            """
            SELECT idempotency_key
            FROM notifications
            WHERE idempotency_key IS NOT NULL
            GROUP BY idempotency_key
            HAVING COUNT(*) > 1
            ORDER BY idempotency_key
            LIMIT 5
            """
        )
    ).fetchall()
    return [str(row[0]) for row in rows if row and row[0] is not None]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "notifications" not in tables:
        return

    columns = _column_names(inspector, "notifications")
    if "idempotency_key" not in columns:
        op.add_column("notifications", sa.Column("idempotency_key", sa.String(), nullable=True))
        columns.add("idempotency_key")

    duplicate_keys = _duplicate_non_null_idempotency_keys(bind)
    if duplicate_keys:
        preview = ", ".join(duplicate_keys)
        raise RuntimeError(
            "Cannot add unique notification idempotency key index because duplicate non-null values exist: "
            f"{preview}"
        )

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "notifications")
    if "ix_notifications_idempotency_key" not in indexes and "idempotency_key" in columns:
        op.create_index(
            "ix_notifications_idempotency_key",
            "notifications",
            ["idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "notifications" not in tables:
        return

    indexes = _index_names(inspector, "notifications")
    if "ix_notifications_idempotency_key" in indexes:
        op.drop_index("ix_notifications_idempotency_key", table_name="notifications")

    columns = _column_names(sa.inspect(bind), "notifications")
    if "idempotency_key" in columns:
        op.drop_column("notifications", "idempotency_key")
