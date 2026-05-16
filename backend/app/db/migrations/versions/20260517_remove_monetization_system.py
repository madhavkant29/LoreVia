"""Defer monetization cleanup until a separately approved destructive rollout.

Revision ID: 20260517_remove_monetization_system
Revises: 20260516_normalize_unique_constraints
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260517_remove_monetization_system"
down_revision: str | None = "20260516_normalize_unique_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Destructive cleanup is intentionally deferred.
    #
    # This revision stays in the graph so later non-destructive schema changes
    # can be applied safely on shared environments without deleting legacy
    # monetization data. When the team is ready to remove those tables and
    # columns, create a new explicitly reviewed destructive migration and run it
    # only after backup/export validation.
    pass


def downgrade() -> None:
    # This placeholder revision does not mutate schema state in either
    # direction. A future explicit cleanup migration can be introduced once the
    # legacy monetization data has been archived and approved for removal.
    pass
