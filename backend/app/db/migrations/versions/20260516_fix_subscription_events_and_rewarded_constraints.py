"""Preserve billing migration order without destructive upgrade steps.

Revision ID: 20260516_fix_subscription_events_and_rewarded_constraints
Revises: 20260516_add_subscription_events
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260516_fix_subscription_events_and_rewarded_constraints"
down_revision: str | None = "20260516_add_subscription_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Forward-only no-op.
    #
    # The preceding migrations already create the relevant subscription event
    # constraint and supporting indexes on fresh databases, and the later
    # normalization migrations reconcile historical drift without requiring any
    # destructive upgrade operations here.
    pass


def downgrade() -> None:
    # This revision no longer mutates schema state.
    pass
