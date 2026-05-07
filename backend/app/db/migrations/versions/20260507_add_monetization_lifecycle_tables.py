"""Add monetization lifecycle tables.

Revision ID: 20260507_add_monetization_lifecycle_tables
Revises: 20260507_add_user_goal_and_login_streak
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260507_add_monetization_lifecycle_tables"
down_revision: str | None = "20260507_add_user_goal_and_login_streak"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" in tables:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "referral_code" not in user_columns:
            op.add_column("users", sa.Column("referral_code", sa.String(), nullable=True))
        user_indexes = _index_names(inspector, "users")
        if "ix_users_referral_code" not in user_indexes:
            op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    created_point_ledger = False
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
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "entry_type", "source_type", "source_id", name="uq_point_ledger_entries_source"),
        )
        tables.add("point_ledger_entries")
        created_point_ledger = True
    if "point_ledger_entries" in tables:
        unique_constraints = (
            set()
            if created_point_ledger
            else {constraint["name"] for constraint in inspector.get_unique_constraints("point_ledger_entries")}
        )
        if "uq_point_ledger_entries_source" not in unique_constraints and not created_point_ledger:
            op.create_unique_constraint(
                "uq_point_ledger_entries_source",
                "point_ledger_entries",
                ["user_id", "entry_type", "source_type", "source_id"],
            )
        indexes = _index_names(inspector, "point_ledger_entries")
        for name, columns in (
            ("ix_point_ledger_entries_user_id", ["user_id"]),
            ("ix_point_ledger_entries_entry_type", ["entry_type"]),
            ("ix_point_ledger_entries_source_type", ["source_type"]),
            ("ix_point_ledger_entries_source_id", ["source_id"]),
            ("ix_point_ledger_entries_expires_at", ["expires_at"]),
            ("ix_point_ledger_entries_created_at", ["created_at"]),
        ):
            if name not in indexes:
                op.create_index(name, "point_ledger_entries", columns)

    if "referrals" not in tables:
        op.create_table(
            "referrals",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("referrer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("referred_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("referral_code", sa.String(), nullable=False),
            sa.Column("status", sa.String(), server_default="pending", nullable=False),
            sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
        )
        tables.add("referrals")
    if "referrals" in tables:
        indexes = _index_names(inspector, "referrals")
        for name, columns in (
            ("ix_referrals_referrer_user_id", ["referrer_user_id"]),
            ("ix_referrals_referred_user_id", ["referred_user_id"]),
            ("ix_referrals_referral_code", ["referral_code"]),
            ("ix_referrals_status", ["status"]),
            ("ix_referrals_created_at", ["created_at"]),
        ):
            if name not in indexes:
                op.create_index(name, "referrals", columns)

    if "trial_email_events" not in tables:
        op.create_table(
            "trial_email_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("email_type", sa.String(), nullable=False),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(), server_default="pending", nullable=False),
            sa.Column("resend_message_id", sa.String(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "email_type", name="uq_trial_email_events_user_type"),
        )
        tables.add("trial_email_events")
    if "trial_email_events" in tables:
        indexes = _index_names(inspector, "trial_email_events")
        for name, columns in (
            ("ix_trial_email_events_user_id", ["user_id"]),
            ("ix_trial_email_events_email_type", ["email_type"]),
            ("ix_trial_email_events_scheduled_for", ["scheduled_for"]),
            ("ix_trial_email_events_status", ["status"]),
            ("ix_trial_email_events_created_at", ["created_at"]),
        ):
            if name not in indexes:
                op.create_index(name, "trial_email_events", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name in ("trial_email_events", "referrals", "point_ledger_entries"):
        if table_name in tables:
            op.drop_table(table_name)

    if "users" in tables:
        user_indexes = _index_names(inspector, "users")
        if "ix_users_referral_code" in user_indexes:
            op.drop_index("ix_users_referral_code", table_name="users")
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "referral_code" in columns:
            op.drop_column("users", "referral_code")
