"""Add subscription lifecycle fields and lifecycle-email idempotency.

Stores the Paddle billing period and scheduled-cancellation state on the local
subscription so renewal reminders, cancellation messaging, and entitlement
decisions no longer depend solely on webhook timing.

Revision ID: 20260919_subscription_lifecycle
Revises: 20260912_public_asset_ready
Create Date: 2026-09-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260919_subscription_lifecycle"
down_revision: str | Sequence[str] | None = "20260912_public_asset_ready"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUBSCRIPTIONS_TABLE = "subscriptions"
EMAIL_EVENTS_TABLE = "subscription_email_events"

ADDED_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    (
        "current_period_start",
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
    ),
    (
        "cancel_at_period_end",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    ),
    (
        "cancellation_scheduled_at",
        sa.Column("cancellation_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    ),
    ("last_payment_status", sa.Column("last_payment_status", sa.String(), nullable=True)),
    (
        "updated_at",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ),
)

INDEXES = (
    ("ix_subscriptions_current_period_end", ["current_period_end"]),
    ("ix_subscriptions_status_cancel_at_period_end", ["status", "cancel_at_period_end"]),
)


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if SUBSCRIPTIONS_TABLE in tables:
        columns = _column_names(inspector, SUBSCRIPTIONS_TABLE)
        if "expires_at" in columns and "current_period_end" not in columns:
            op.alter_column(
                SUBSCRIPTIONS_TABLE,
                "expires_at",
                new_column_name="current_period_end",
            )
            columns.discard("expires_at")
            columns.add("current_period_end")
        elif "current_period_end" not in columns:
            op.add_column(
                SUBSCRIPTIONS_TABLE,
                sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
            )
            columns.add("current_period_end")

        for column_name, column in ADDED_COLUMNS:
            if column_name not in columns:
                op.add_column(SUBSCRIPTIONS_TABLE, column)
                columns.add(column_name)

        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, SUBSCRIPTIONS_TABLE)
        for index_name, index_columns in INDEXES:
            if index_name not in indexes:
                op.create_index(index_name, SUBSCRIPTIONS_TABLE, index_columns)

    inspector = sa.inspect(bind)
    if EMAIL_EVENTS_TABLE not in _table_names(inspector):
        op.create_table(
            EMAIL_EVENTS_TABLE,
            sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "subscription_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("email_type", sa.String(), nullable=False),
            sa.Column("billing_period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column(
                "metadata_json",
                JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "subscription_id",
                "email_type",
                "billing_period_end",
                name="uq_subscription_email_events_period",
            ),
        )
        op.create_index("ix_subscription_email_events_user_id", EMAIL_EVENTS_TABLE, ["user_id"])
        op.create_index(
            "ix_subscription_email_events_subscription_id",
            EMAIL_EVENTS_TABLE,
            ["subscription_id"],
        )
        op.create_index(
            "ix_subscription_email_events_email_type", EMAIL_EVENTS_TABLE, ["email_type"]
        )
        op.create_index(
            "ix_subscription_email_events_billing_period_end",
            EMAIL_EVENTS_TABLE,
            ["billing_period_end"],
        )
        op.create_index(
            "ix_subscription_email_events_status_scheduled_for",
            EMAIL_EVENTS_TABLE,
            ["status", "scheduled_for"],
        )
        op.create_index(
            "ix_subscription_email_events_created_at", EMAIL_EVENTS_TABLE, ["created_at"]
        )

    # Reconcile indexes for tables that were created before this revision or
    # by the baseline metadata: the ORM declares a single-column index on
    # ``status`` that the create-table path above does not emit.
    inspector = sa.inspect(bind)
    if EMAIL_EVENTS_TABLE in _table_names(inspector):
        email_indexes = _index_names(inspector, EMAIL_EVENTS_TABLE)
        if "ix_subscription_email_events_status" not in email_indexes:
            op.create_index("ix_subscription_email_events_status", EMAIL_EVENTS_TABLE, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if EMAIL_EVENTS_TABLE in tables:
        op.drop_table(EMAIL_EVENTS_TABLE)

    inspector = sa.inspect(bind)
    if SUBSCRIPTIONS_TABLE in tables:
        indexes = _index_names(inspector, SUBSCRIPTIONS_TABLE)
        for index_name, _index_columns in INDEXES:
            if index_name in indexes:
                op.drop_index(index_name, table_name=SUBSCRIPTIONS_TABLE)

        columns = _column_names(inspector, SUBSCRIPTIONS_TABLE)
        for column_name, _column in ADDED_COLUMNS:
            if column_name in columns:
                op.drop_column(SUBSCRIPTIONS_TABLE, column_name)
        if "current_period_end" in columns and "expires_at" not in columns:
            op.alter_column(
                SUBSCRIPTIONS_TABLE,
                "current_period_end",
                new_column_name="expires_at",
            )
