"""Add durable Paddle webhook inbox table.

Revision ID: 20260518_add_paddle_webhook_events
Revises: 20260517_add_notification_idempotency_key
Create Date: 2026-05-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260518_add_paddle_webhook_events"
down_revision: str | None = "20260517_add_notification_idempotency_key"
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

    if "paddle_webhook_events" not in tables:
        op.create_table(
            "paddle_webhook_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("notification_id", sa.String(), nullable=True),
            sa.Column("processing_status", sa.String(), nullable=False, server_default="processing"),
            sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("first_received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_id", name="uq_paddle_webhook_events_event_id"),
        )

    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "paddle_webhook_events")
    indexes = _index_names(inspector, "paddle_webhook_events")
    unique_constraints = _unique_constraint_names(inspector, "paddle_webhook_events")

    if "uq_paddle_webhook_events_event_id" not in unique_constraints and "event_id" in columns:
        op.create_unique_constraint(
            "uq_paddle_webhook_events_event_id",
            "paddle_webhook_events",
            ["event_id"],
        )

    for index_name, column_name in (
        ("ix_paddle_webhook_events_event_id", "event_id"),
        ("ix_paddle_webhook_events_event_type", "event_type"),
        ("ix_paddle_webhook_events_processing_status", "processing_status"),
        ("ix_paddle_webhook_events_first_received_at", "first_received_at"),
        ("ix_paddle_webhook_events_processed_at", "processed_at"),
    ):
        if column_name in columns and index_name not in indexes:
            op.create_index(index_name, "paddle_webhook_events", [column_name], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "paddle_webhook_events" not in tables:
        return

    indexes = _index_names(inspector, "paddle_webhook_events")
    for index_name in (
        "ix_paddle_webhook_events_processed_at",
        "ix_paddle_webhook_events_first_received_at",
        "ix_paddle_webhook_events_processing_status",
        "ix_paddle_webhook_events_event_type",
        "ix_paddle_webhook_events_event_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="paddle_webhook_events")

    op.drop_table("paddle_webhook_events")
