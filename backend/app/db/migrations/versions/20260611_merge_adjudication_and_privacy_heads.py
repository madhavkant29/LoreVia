"""Merge character candidate adjudication and privacy deletion state heads.

Revision ID: 20260611_merge_adjudication_and_privacy_heads
Revises: 20260611_add_character_candidate_adjudication, 20260611_privacy_deletion_state
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260611_merge_adjudication_and_privacy_heads"
down_revision: tuple[str, str] | None = (
    "20260611_add_character_candidate_adjudication",
    "20260611_privacy_deletion_state",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
