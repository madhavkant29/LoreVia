"""add email verification to users

Revision ID: 20260505_add_email_verification_to_users
Revises: 20260503_add_world_canonical_identities
Create Date: 2026-05-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260505_add_email_verification_to_users"
down_revision: str | None = "20260503_add_world_canonical_identities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"] for col in inspector.get_columns("users")}
    if "email_verified_at" not in columns:
        op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(sa.text("UPDATE users SET email_verified_at = NOW() WHERE email_verified_at IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"] for col in inspector.get_columns("users")}
    if "email_verified_at" in columns:
        op.drop_column("users", "email_verified_at")
