"""Match ORM unique index metadata for billing tables.

Revision ID: 20260516_adjust_unique_indexes
Revises: 20260516_fix_subscription_events_and_rewarded_constraints
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260516_adjust_unique_indexes"
down_revision: str | None = "20260516_fix_subscription_events_and_rewarded_constraints"
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
        if "uq_rewarded_ad_sessions_claim_token" in unique_constraints:
            op.drop_constraint(
                "uq_rewarded_ad_sessions_claim_token",
                "rewarded_ad_sessions",
                type_="unique",
            )

        index_names = {index["name"] for index in inspector.get_indexes("rewarded_ad_sessions")}
        if "ix_rewarded_ad_sessions_claim_token" not in index_names:
            op.create_index(
                "ix_rewarded_ad_sessions_claim_token",
                "rewarded_ad_sessions",
                ["claim_token"],
                unique=True,
            )

    if "subscription_events" in tables:
        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("subscription_events")
        }
        if "uq_subscription_events_source_event_id" in unique_constraints:
            op.drop_constraint(
                "uq_subscription_events_source_event_id",
                "subscription_events",
                type_="unique",
            )

        index_names = {index["name"] for index in inspector.get_indexes("subscription_events")}
        if "ix_subscription_events_source_event_id" in index_names:
            op.drop_index("ix_subscription_events_source_event_id", table_name="subscription_events")
        op.create_index(
            "ix_subscription_events_source_event_id",
            "subscription_events",
            ["source_event_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "subscription_events" in tables:
        index_names = {index["name"] for index in inspector.get_indexes("subscription_events")}
        if "ix_subscription_events_source_event_id" in index_names:
            op.drop_index("ix_subscription_events_source_event_id", table_name="subscription_events")
        op.create_unique_constraint(
            "uq_subscription_events_source_event_id",
            "subscription_events",
            ["source_event_id"],
        )
        op.create_index(
            "ix_subscription_events_source_event_id",
            "subscription_events",
            ["source_event_id"],
        )

    if "rewarded_ad_sessions" in tables:
        index_names = {index["name"] for index in inspector.get_indexes("rewarded_ad_sessions")}
        if "ix_rewarded_ad_sessions_claim_token" in index_names:
            op.drop_index("ix_rewarded_ad_sessions_claim_token", table_name="rewarded_ad_sessions")
        op.create_unique_constraint(
            "uq_rewarded_ad_sessions_claim_token",
            "rewarded_ad_sessions",
            ["claim_token"],
        )
        op.create_index(
            "ix_rewarded_ad_sessions_claim_token",
            "rewarded_ad_sessions",
            ["claim_token"],
        )
