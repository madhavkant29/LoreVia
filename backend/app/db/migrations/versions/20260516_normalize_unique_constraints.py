"""Normalize unique constraints to a constraint-first convention.

Revision ID: 20260516_normalize_unique_constraints
Revises: 20260516_add_rewarded_claim_token_constraint
Create Date: 2026-05-16

This migration is intentionally forward-only. It aligns named uniqueness
constraints with the ORM metadata while preserving existing live semantics.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260516_normalize_unique_constraints"
down_revision: str | None = "20260516_add_rewarded_claim_token_constraint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


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


def _index_is_owned_by_constraint(index_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint con
            JOIN pg_class idx ON idx.oid = con.conindid
            JOIN pg_namespace nsp ON nsp.oid = idx.relnamespace
            WHERE nsp.nspname = 'public'
              AND idx.relname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    )
    return result.scalar() is not None


def _add_constraint_using_index_if_missing(
    inspector: sa.Inspector,
    table_name: str,
    constraint_name: str,
    index_name: str,
    columns: list[str],
) -> None:
    unique_constraints = _unique_constraint_names(inspector, table_name)
    if constraint_name in unique_constraints:
        return

    indexes = _index_names(inspector, table_name)
    if index_name in indexes:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" '
                f'ADD CONSTRAINT "{constraint_name}" UNIQUE USING INDEX "{index_name}"'
            )
        )
        return

    op.create_unique_constraint(constraint_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    constraint_specs = (
        ("users", "uq_users_email", "ix_users_email", ["email"]),
        ("users", "uq_users_username", "ix_users_username", ["username"]),
        ("users", "uq_users_referral_code", "ix_users_referral_code", ["referral_code"]),
        (
            "character_voice_profiles",
            "uq_character_voice_profiles_character_id",
            "ix_character_voice_profiles_character_id",
            ["character_id"],
        ),
        (
            "subscription_events",
            "uq_subscription_events_source_event_id",
            "ix_subscription_events_source_event_id",
            ["source_event_id"],
        ),
        (
            "user_rate_limit_overrides",
            "uq_user_rate_limit_overrides_user_id",
            "ix_user_rate_limit_overrides_user_id",
            ["user_id"],
        ),
        ("referrals", "uq_referrals_referred_user_id", "ix_referrals_referred_user_id", ["referred_user_id"]),
    )

    for table_name, constraint_name, index_name, columns in constraint_specs:
        if table_name in tables:
            _add_constraint_using_index_if_missing(inspector, table_name, constraint_name, index_name, columns)
            inspector = sa.inspect(bind)

    if "rewarded_ad_sessions" in tables:
        unique_constraints = _unique_constraint_names(inspector, "rewarded_ad_sessions")
        had_constraint_before = "uq_rewarded_ad_sessions_claim_token" in unique_constraints
        if not had_constraint_before:
            indexes = _index_names(inspector, "rewarded_ad_sessions")
            if "ix_rewarded_ad_sessions_claim_token" in indexes:
                op.execute(
                    sa.text(
                        'ALTER TABLE "rewarded_ad_sessions" '
                        'ADD CONSTRAINT "uq_rewarded_ad_sessions_claim_token" '
                        'UNIQUE USING INDEX "ix_rewarded_ad_sessions_claim_token"'
                    )
                )
            else:
                op.create_unique_constraint(
                    "uq_rewarded_ad_sessions_claim_token",
                    "rewarded_ad_sessions",
                    ["claim_token"],
                )
            inspector = sa.inspect(bind)

        indexes = _index_names(inspector, "rewarded_ad_sessions")
        if (
            had_constraint_before
            and "ix_rewarded_ad_sessions_claim_token" in indexes
            and not _index_is_owned_by_constraint("ix_rewarded_ad_sessions_claim_token")
        ):
            op.drop_index("ix_rewarded_ad_sessions_claim_token", table_name="rewarded_ad_sessions")


def downgrade() -> None:
    # Forward-only cleanup migration. Historical uniqueness/index representation
    # is intentionally not restored during downgrade.
    pass
