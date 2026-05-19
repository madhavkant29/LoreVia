"""Restore the rewarded ad claim token unique constraint.

Revision ID: 20260516_add_rewarded_claim_token_constraint
Revises: 20260516_adjust_unique_indexes
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260516_add_rewarded_claim_token_constraint"
down_revision: str | None = "20260516_adjust_unique_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rewarded_ad_sessions" not in tables:
        return

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("rewarded_ad_sessions")
    }
    if "uq_rewarded_ad_sessions_claim_token" not in unique_constraints:
        op.create_unique_constraint(
            "uq_rewarded_ad_sessions_claim_token",
            "rewarded_ad_sessions",
            ["claim_token"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rewarded_ad_sessions" not in tables:
        return

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
