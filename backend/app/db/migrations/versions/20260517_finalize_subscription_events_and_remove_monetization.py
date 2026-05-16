"""Finalize subscription events and remove legacy monetization tables.

Revision ID: 20260517_finalize_subscription_events_and_remove_monetization
Revises: 20260517_merge_safe_schema_heads
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260517_finalize_subscription_events_and_remove_monetization"
down_revision: str | None = "20260517_merge_safe_schema_heads"
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


def _drop_index_if_present(inspector: sa.Inspector, table_name: str, index_name: str) -> None:
    if table_name in _table_names(inspector) and index_name in _index_names(inspector, table_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_constraint_if_present(inspector: sa.Inspector, table_name: str, constraint_name: str) -> None:
    if table_name in _table_names(inspector) and constraint_name in _unique_constraint_names(inspector, table_name):
        op.drop_constraint(constraint_name, table_name, type_="unique")


def _ensure_subscription_events(bind: sa.Connection) -> None:
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
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_event_id", name="uq_subscription_events_source_event_id"),
        )
        inspector = sa.inspect(bind)

    columns = _column_names(inspector, "subscription_events")
    expected_columns: dict[str, sa.Column] = {
        "source": sa.Column("source", sa.String(), server_default="paddle", nullable=False),
        "source_event_id": sa.Column("source_event_id", sa.String(), nullable=True),
        "plan": sa.Column("plan", sa.String(), nullable=True),
        "status": sa.Column("status", sa.String(), nullable=True),
        "paddle_customer_id": sa.Column("paddle_customer_id", sa.String(), nullable=True),
        "paddle_sub_id": sa.Column("paddle_sub_id", sa.String(), nullable=True),
        "metadata_json": sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        "occurred_at": sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        "created_at": sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    }
    for column_name, column in expected_columns.items():
        if column_name not in columns:
            op.add_column("subscription_events", column)
            inspector = sa.inspect(bind)
            columns = _column_names(inspector, "subscription_events")

    unique_constraints = _unique_constraint_names(inspector, "subscription_events")
    if "uq_subscription_events_source_event_id" not in unique_constraints:
        op.create_unique_constraint(
            "uq_subscription_events_source_event_id",
            "subscription_events",
            ["source_event_id"],
        )
        inspector = sa.inspect(bind)

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
            inspector = sa.inspect(bind)
            indexes = _index_names(inspector, "subscription_events")


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_subscription_events(bind)

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "users" in tables:
        _drop_constraint_if_present(inspector, "users", "uq_users_referral_code")
        inspector = sa.inspect(bind)
        _drop_index_if_present(inspector, "users", "ix_users_referral_code")
        inspector = sa.inspect(bind)
        if "referral_code" in _column_names(inspector, "users"):
            op.drop_column("users", "referral_code")
            inspector = sa.inspect(bind)
            tables = _table_names(inspector)

    for table_name in ("rewarded_ad_sessions", "referrals", "point_ledger_entries"):
        if table_name in tables:
            op.drop_table(table_name)
            inspector = sa.inspect(bind)
            tables = _table_names(inspector)

    if "beta_read_assignments" in tables:
        columns = _column_names(inspector, "beta_read_assignments")
        indexes = _index_names(inspector, "beta_read_assignments")
        if "ix_beta_read_assignments_awarded_at" in indexes:
            op.drop_index("ix_beta_read_assignments_awarded_at", table_name="beta_read_assignments")
            inspector = sa.inspect(bind)
            columns = _column_names(inspector, "beta_read_assignments")
        for column_name in ("awarded_at", "awarded_points", "reward_points"):
            if column_name in columns:
                op.drop_column("beta_read_assignments", column_name)
                inspector = sa.inspect(bind)
                columns = _column_names(inspector, "beta_read_assignments")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "users" in tables:
        columns = _column_names(inspector, "users")
        if "referral_code" not in columns:
            op.add_column("users", sa.Column("referral_code", sa.String(), nullable=True))
            inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "users")
        if "ix_users_referral_code" not in indexes:
            op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    if "point_ledger_entries" not in tables:
        op.create_table(
            "point_ledger_entries",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entry_type", sa.String(), nullable=False),
            sa.Column("source_type", sa.String(), nullable=False),
            sa.Column("source_id", sa.String(), nullable=True),
            sa.Column("points_delta", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "entry_type", "source_type", "source_id", name="uq_point_ledger_entries_source"),
        )
        op.create_index("ix_point_ledger_entries_user_id", "point_ledger_entries", ["user_id"])
        op.create_index("ix_point_ledger_entries_entry_type", "point_ledger_entries", ["entry_type"])
        op.create_index("ix_point_ledger_entries_source_type", "point_ledger_entries", ["source_type"])
        op.create_index("ix_point_ledger_entries_source_id", "point_ledger_entries", ["source_id"])
        op.create_index("ix_point_ledger_entries_expires_at", "point_ledger_entries", ["expires_at"])
        op.create_index("ix_point_ledger_entries_created_at", "point_ledger_entries", ["created_at"])
        inspector = sa.inspect(bind)
        tables = _table_names(inspector)

    if "referrals" not in tables:
        op.create_table(
            "referrals",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("referrer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("referred_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("referral_code", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
        )
        op.create_index("ix_referrals_referrer_user_id", "referrals", ["referrer_user_id"])
        op.create_index("ix_referrals_referral_code", "referrals", ["referral_code"])
        op.create_index("ix_referrals_status", "referrals", ["status"])
        op.create_index("ix_referrals_created_at", "referrals", ["created_at"])
        inspector = sa.inspect(bind)
        tables = _table_names(inspector)

    if "rewarded_ad_sessions" not in tables:
        op.create_table(
            "rewarded_ad_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("claim_token", sa.String(), nullable=False),
            sa.Column("ad_unit_path", sa.String(), nullable=False),
            sa.Column("placement", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("reward_points", sa.Integer(), nullable=False),
            sa.Column("reward_granted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("claim_token", name="uq_rewarded_ad_sessions_claim_token"),
        )
        op.create_index("ix_rewarded_ad_sessions_user_id", "rewarded_ad_sessions", ["user_id"])
        op.create_index("ix_rewarded_ad_sessions_provider", "rewarded_ad_sessions", ["provider"])
        op.create_index("ix_rewarded_ad_sessions_placement", "rewarded_ad_sessions", ["placement"])
        op.create_index("ix_rewarded_ad_sessions_status", "rewarded_ad_sessions", ["status"])
        op.create_index("ix_rewarded_ad_sessions_reward_granted_at", "rewarded_ad_sessions", ["reward_granted_at"])
        op.create_index("ix_rewarded_ad_sessions_expires_at", "rewarded_ad_sessions", ["expires_at"])
        op.create_index("ix_rewarded_ad_sessions_created_at", "rewarded_ad_sessions", ["created_at"])

    inspector = sa.inspect(bind)
    if "beta_read_assignments" in _table_names(inspector):
        columns = _column_names(inspector, "beta_read_assignments")
        if "reward_points" not in columns:
            op.add_column(
                "beta_read_assignments",
                sa.Column("reward_points", sa.Integer(), nullable=False, server_default="0"),
            )
            inspector = sa.inspect(bind)
            columns = _column_names(inspector, "beta_read_assignments")
        if "awarded_points" not in columns:
            op.add_column(
                "beta_read_assignments",
                sa.Column("awarded_points", sa.Integer(), nullable=False, server_default="0"),
            )
            inspector = sa.inspect(bind)
            columns = _column_names(inspector, "beta_read_assignments")
        if "awarded_at" not in columns:
            op.add_column("beta_read_assignments", sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True))
            inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "beta_read_assignments")
        if "ix_beta_read_assignments_awarded_at" not in indexes:
            op.create_index("ix_beta_read_assignments_awarded_at", "beta_read_assignments", ["awarded_at"])

    inspector = sa.inspect(bind)
    if "subscription_events" in _table_names(inspector):
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
                inspector = sa.inspect(bind)
                indexes = _index_names(inspector, "subscription_events")
        op.drop_table("subscription_events")
