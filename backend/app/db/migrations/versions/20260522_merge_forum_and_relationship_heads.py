"""Merge forum reply and relationship review migration heads.

Revision ID: 20260522_merge_forum_and_relationship_heads
Revises: 20260522_add_forum_comment_replies, 20260522_relationship_review
Create Date: 2026-05-22
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260522_merge_forum_and_relationship_heads"
down_revision: tuple[str, str] | None = (
    "20260522_add_forum_comment_replies",
    "20260522_relationship_review",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
