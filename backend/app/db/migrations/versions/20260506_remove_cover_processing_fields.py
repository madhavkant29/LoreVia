"""Document removal of legacy processed cover fields from books.

Revision ID: 20260506_remove_cover_processing_fields
Revises: 20260505_update_device_trial_index
Create Date: 2026-05-06 00:00:00.000000
"""

from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = "20260506_remove_cover_processing_fields"
down_revision: str | None = "20260505_update_device_trial_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh databases already inherit the current schema from the baseline
    # migration, so this historical cleanup revision stays non-destructive.
    pass


def downgrade() -> None:
    # Historical placeholder revision; no downgrade action is needed.
    pass
