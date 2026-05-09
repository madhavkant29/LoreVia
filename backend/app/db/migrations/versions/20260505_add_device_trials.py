"""Add device trial table for free-signup enforcement.

Revision ID: 20260505_add_device_trials
Revises: 20260505_add_email_verification_to_users
Create Date: 2026-05-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260505_add_device_trials"
down_revision: str | None = "20260505_add_email_verification_to_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "device_trials" not in tables:
        op.create_table(
            "device_trials",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("device_id_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("device_trials")} if "device_trials" in set(inspector.get_table_names()) else set()
    if "ix_device_trials_user_id" not in indexes:
        op.create_index("ix_device_trials_user_id", "device_trials", ["user_id"], unique=False)
    if "ix_device_trials_device_id_hash" not in indexes:
        op.create_index("ix_device_trials_device_id_hash", "device_trials", ["device_id_hash"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "device_trials" not in tables:
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("device_trials")}
    if "ix_device_trials_device_id_hash" in indexes:
        op.drop_index("ix_device_trials_device_id_hash", table_name="device_trials")
    if "ix_device_trials_user_id" in indexes:
        op.drop_index("ix_device_trials_user_id", table_name="device_trials")
    op.drop_table("device_trials")
