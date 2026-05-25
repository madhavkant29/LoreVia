"""Add refund review records for guarded Paddle refunds.

Revision ID: 20260524_add_refund_reviews
Revises: 20260524_add_public_book_rankings
Create Date: 2026-05-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260524_add_refund_reviews"
down_revision: str | None = "20260524_add_public_book_rankings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACTIVE_STATUSES = (
    "pending_evaluation",
    "manual_review_required",
    "approved_pending_provider",
    "provider_followup_required",
)


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

    if "refund_reviews" not in tables:
        op.create_table(
            "refund_reviews",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("paddle_transaction_id", sa.String(), nullable=False),
            sa.Column("paddle_adjustment_id", sa.String(), nullable=True),
            sa.Column("charge_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("plan_code", sa.String(), nullable=False),
            sa.Column("billing_interval", sa.String(), nullable=False),
            sa.Column("request_source", sa.String(), nullable=False),
            sa.Column("support_reference", sa.String(), nullable=True),
            sa.Column("request_reason", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("auto_decision", sa.Boolean(), nullable=True),
            sa.Column("decision_reason", sa.Text(), nullable=True),
            sa.Column(
                "eligibility_snapshot_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "usage_snapshot_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "provider_response_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("requested_by_admin_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resolved_by_admin_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["requested_by_admin_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["resolved_by_admin_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if "refund_reviews" not in _table_names(inspector):
        return

    columns = _column_names(inspector, "refund_reviews")
    indexes = _index_names(inspector, "refund_reviews")

    for index_name, column_names in (
        ("ix_refund_reviews_user_id", ["user_id"]),
        ("ix_refund_reviews_subscription_id", ["subscription_id"]),
        ("ix_refund_reviews_paddle_transaction_id", ["paddle_transaction_id"]),
        ("ix_refund_reviews_paddle_adjustment_id", ["paddle_adjustment_id"]),
        ("ix_refund_reviews_charge_at", ["charge_at"]),
        ("ix_refund_reviews_plan_code", ["plan_code"]),
        ("ix_refund_reviews_billing_interval", ["billing_interval"]),
        ("ix_refund_reviews_request_source", ["request_source"]),
        ("ix_refund_reviews_support_reference", ["support_reference"]),
        ("ix_refund_reviews_status", ["status"]),
        ("ix_refund_reviews_requested_by_admin_user_id", ["requested_by_admin_user_id"]),
        ("ix_refund_reviews_resolved_by_admin_user_id", ["resolved_by_admin_user_id"]),
        ("ix_refund_reviews_resolved_at", ["resolved_at"]),
        ("ix_refund_reviews_created_at", ["created_at"]),
        ("ix_refund_reviews_updated_at", ["updated_at"]),
    ):
        if all(column_name in columns for column_name in column_names) and index_name not in indexes:
            op.create_index(index_name, "refund_reviews", column_names, unique=False)

    if "uq_refund_reviews_active_transaction" not in indexes and "paddle_transaction_id" in columns and "status" in columns:
        op.create_index(
            "uq_refund_reviews_active_transaction",
            "refund_reviews",
            ["paddle_transaction_id"],
            unique=True,
            postgresql_where=sa.text(
                "status IN ('pending_evaluation', 'manual_review_required', 'approved_pending_provider', 'provider_followup_required')"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "refund_reviews" not in tables:
        return

    indexes = _index_names(inspector, "refund_reviews")
    for index_name in (
        "uq_refund_reviews_active_transaction",
        "ix_refund_reviews_updated_at",
        "ix_refund_reviews_created_at",
        "ix_refund_reviews_resolved_at",
        "ix_refund_reviews_resolved_by_admin_user_id",
        "ix_refund_reviews_requested_by_admin_user_id",
        "ix_refund_reviews_status",
        "ix_refund_reviews_support_reference",
        "ix_refund_reviews_request_source",
        "ix_refund_reviews_billing_interval",
        "ix_refund_reviews_plan_code",
        "ix_refund_reviews_charge_at",
        "ix_refund_reviews_paddle_adjustment_id",
        "ix_refund_reviews_paddle_transaction_id",
        "ix_refund_reviews_subscription_id",
        "ix_refund_reviews_user_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="refund_reviews")

    op.drop_table("refund_reviews")
