"""Merge the safe schema branches into a single head.

Revision ID: 20260517_merge_safe_schema_heads
Revises: 20260516_add_public_share_approval_fields, 20260516_optimize_public_forum_reads, 20260517_allow_multiple_public_forum_posts_per_book
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260517_merge_safe_schema_heads"
down_revision: tuple[str, ...] = (
    "20260516_add_public_share_approval_fields",
    "20260516_optimize_public_forum_reads",
    "20260517_allow_multiple_public_forum_posts_per_book",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
