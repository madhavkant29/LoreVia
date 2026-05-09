"""Document legacy processed cover fields for historical compatibility.

Revision ID: 20260428_cover_processing_fields
Revises: 20260427_add_username_to_users
Create Date: 2026-04-28 00:00:00.000000
"""

from collections.abc import Sequence


revision: str = "20260428_cover_processing_fields"
down_revision: str | None = "20260427_add_username_to_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The baseline schema already reflects the current Book model and does not
    # include these legacy cover-processing columns. Keep this revision as a
    # no-op so fresh databases do not reintroduce retired fields.
    pass


def downgrade() -> None:
    # Historical placeholder revision; no downgrade action is needed.
    pass
