"""Keep billing revision history while deferring uniqueness normalization.

Revision ID: 20260516_adjust_unique_indexes
Revises: 20260516_fix_subscription_events_and_rewarded_constraints
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260516_adjust_unique_indexes"
down_revision: str | None = "20260516_fix_subscription_events_and_rewarded_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Forward-only no-op.
    #
    # The later normalization revisions keep the final schema aligned with ORM
    # metadata using additive or explicitly-reviewed operations. Leaving this
    # revision empty avoids destructive upgrade steps that would otherwise be
    # blocked by the repository's Alembic safety guard.
    pass


def downgrade() -> None:
    # This revision no longer mutates schema state.
    pass
