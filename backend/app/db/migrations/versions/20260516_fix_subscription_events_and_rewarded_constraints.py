"""Align billing tables with current ORM metadata.

Revision ID: 20260516_fix_subscription_events_and_rewarded_constraints
Revises: 20260516_add_subscription_events
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260516_fix_subscription_events_and_rewarded_constraints"
down_revision: str | None = "20260516_add_subscription_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rewarded_ad_sessions" in tables:
        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("rewarded_ad_sessions")
        }
        if "uq_rewarded_ad_sessions_claim_token" not in unique_constraints:
            op.execute(
                'ALTER TABLE "rewarded_ad_sessions" '
                'ADD CONSTRAINT "uq_rewarded_ad_sessions_claim_token" '
                'UNIQUE USING INDEX "ix_rewarded_ad_sessions_claim_token"'
            )

    if "users" in tables:
        index_names = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_beta_read_penalty_required_at" in index_names:
            op.drop_index("ix_users_beta_read_penalty_required_at", table_name="users")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" in tables:
        index_names = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_beta_read_penalty_required_at" not in index_names:
            op.create_index(
                "ix_users_beta_read_penalty_required_at",
                "users",
                ["beta_read_penalty_required_at"],
            )

    if "rewarded_ad_sessions" in tables:
        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("rewarded_ad_sessions")
        }
        if "uq_rewarded_ad_sessions_claim_token" in unique_constraints:
            op.drop_constraint(
                "uq_rewarded_ad_sessions_claim_token",
                "rewarded_ad_sessions",
                type_="unique",
            )
