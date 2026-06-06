"""Enforce unique device-to-user links in device_trials.

Revision ID: 20260602_enforce_device_trial_user_uniqueness
Revises: 20260602_add_book_upload_charges
Create Date: 2026-06-02 09:00:00.000000

Preflight (run on production DB before deploying this migration):
    SELECT COUNT(*) FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY user_id, device_id_hash
            ORDER BY created_at NULLS LAST, id
        ) AS rn
        FROM device_trials
    ) ranked WHERE rn > 1;

DATA LOSS WARNING: upgrade() deletes duplicate (user_id, device_id_hash) rows.
downgrade() drops the unique constraint but CANNOT restore deleted rows.
This migration is irreversible in terms of data — preflight the duplicate count
before running.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260602_enforce_device_trial_user_uniqueness"
down_revision: str | None = "20260602_add_book_upload_charges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "uq_device_trials_user_device"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "device_trials" not in tables:
        return

    op.execute(
        sa.text(
            """
            DELETE FROM device_trials AS target
            USING (
                SELECT id
                FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY user_id, device_id_hash
                            ORDER BY created_at NULLS LAST, id
                        ) AS rn
                    FROM device_trials
                ) AS ranked
                WHERE ranked.rn > 1
            ) AS duplicates
            WHERE target.id = duplicates.id
            """
        )
    )

    inspector = sa.inspect(bind)
    unique_constraints = {item["name"] for item in inspector.get_unique_constraints("device_trials")}
    indexes = {item["name"] for item in inspector.get_indexes("device_trials")}
    if CONSTRAINT_NAME not in unique_constraints and CONSTRAINT_NAME not in indexes:
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            "device_trials",
            ["user_id", "device_id_hash"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "device_trials" not in tables:
        return

    unique_constraints = {item["name"] for item in inspector.get_unique_constraints("device_trials")}
    if CONSTRAINT_NAME in unique_constraints:
        op.drop_constraint(CONSTRAINT_NAME, "device_trials", type_="unique")
