"""Merge all migration heads into a single linear history.

Revision ID: 20260429_merge_all_heads
Revises: 20260426_char_type, 20260429_merge_migration_heads
Create Date: 2026-04-29 00:00:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260429_merge_all_heads"
down_revision: tuple[str, str] | None = (
    "20260426_char_type",
    "20260429_merge_migration_heads",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
