"""Add subscription event history for monetization metrics.

Revision ID: 20260516_add_subscription_events
Revises: 20260516_align_schema_with_models
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260516_add_subscription_events"
down_revision: str | None = "20260516_align_schema_with_models"
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

    if "subscription_events" not in tables:
        op.create_table(
            "subscription_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("source", sa.String(), server_default="paddle", nullable=False),
            sa.Column("source_event_id", sa.String(), nullable=True),
            sa.Column("plan", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("paddle_customer_id", sa.String(), nullable=True),
            sa.Column("paddle_sub_id", sa.String(), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_event_id", name="uq_subscription_events_source_event_id"),
        )
        tables.add("subscription_events")

    if "subscription_events" not in tables:
        return

    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "subscription_events")
    expected_columns: dict[str, sa.Column] = {
        "source": sa.Column("source", sa.String(), server_default="paddle", nullable=False),
        "source_event_id": sa.Column("source_event_id", sa.String(), nullable=True),
        "plan": sa.Column("plan", sa.String(), nullable=True),
        "status": sa.Column("status", sa.String(), nullable=True),
        "paddle_customer_id": sa.Column("paddle_customer_id", sa.String(), nullable=True),
        "paddle_sub_id": sa.Column("paddle_sub_id", sa.String(), nullable=True),
        "metadata_json": sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        "occurred_at": sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        "created_at": sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    }
    for column_name, column in expected_columns.items():
        if column_name not in columns:
            op.add_column("subscription_events", column)

    unique_constraints = _unique_constraint_names(inspector, "subscription_events")
    if "uq_subscription_events_source_event_id" not in unique_constraints:
        op.create_unique_constraint(
            "uq_subscription_events_source_event_id",
            "subscription_events",
            ["source_event_id"],
        )

    indexes = _index_names(inspector, "subscription_events")
    for name, columns_list in (
        ("ix_subscription_events_user_id", ["user_id"]),
        ("ix_subscription_events_event_type", ["event_type"]),
        ("ix_subscription_events_source", ["source"]),
        ("ix_subscription_events_source_event_id", ["source_event_id"]),
        ("ix_subscription_events_plan", ["plan"]),
        ("ix_subscription_events_status", ["status"]),
        ("ix_subscription_events_paddle_customer_id", ["paddle_customer_id"]),
        ("ix_subscription_events_paddle_sub_id", ["paddle_sub_id"]),
        ("ix_subscription_events_occurred_at", ["occurred_at"]),
        ("ix_subscription_events_created_at", ["created_at"]),
    ):
        if name not in indexes:
            op.create_index(name, "subscription_events", columns_list, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "subscription_events" not in tables:
        return

    indexes = _index_names(inspector, "subscription_events")
    for index_name in (
        "ix_subscription_events_created_at",
        "ix_subscription_events_occurred_at",
        "ix_subscription_events_paddle_sub_id",
        "ix_subscription_events_paddle_customer_id",
        "ix_subscription_events_status",
        "ix_subscription_events_plan",
        "ix_subscription_events_source_event_id",
        "ix_subscription_events_source",
        "ix_subscription_events_event_type",
        "ix_subscription_events_user_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="subscription_events")

    op.drop_table("subscription_events")
