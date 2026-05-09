"""Document the non-unique device trial index state.

Revision ID: 20260505_update_device_trial_index
Revises: 20260505_add_device_trials
Create Date: 2026-05-05 00:30:00.000000
"""

from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = "20260505_update_device_trial_index"
down_revision: str | None = "20260505_add_device_trials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The preceding migration already creates ix_device_trials_device_id_hash
    # as a non-unique index, so a fresh upgrade path needs no schema change here.
    pass


def downgrade() -> None:
    pass
