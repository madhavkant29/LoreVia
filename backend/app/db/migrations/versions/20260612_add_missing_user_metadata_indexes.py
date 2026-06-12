"""Add user indexes reflected in ORM metadata.

Revision ID: 20260612_add_missing_user_metadata_indexes
Revises: 20260612_fix_book_upload_charge_created_at_nullable
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260612_add_missing_user_metadata_indexes"
down_revision: str | Sequence[str] | None = "20260612_fix_book_upload_charge_created_at_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


USERS_TABLE = "users"


def _index_names(inspector: sa.Inspector) -> set[str]:
    if USERS_TABLE not in set(inspector.get_table_names()):
        return set()
    return {
        name
        for index in inspector.get_indexes(USERS_TABLE)
        if isinstance(name := index.get("name"), str)
    }


def _column_names(inspector: sa.Inspector) -> set[str]:
    if USERS_TABLE not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(USERS_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector)
    indexes = _index_names(inspector)

    if "username" in columns and "ix_users_username" not in indexes:
        op.create_index("ix_users_username", USERS_TABLE, ["username"], unique=True)
    if "beta_read_penalty_required_at" in columns and "ix_users_beta_read_penalty_required_at" not in indexes:
        op.create_index(
            "ix_users_beta_read_penalty_required_at",
            USERS_TABLE,
            ["beta_read_penalty_required_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = _index_names(inspector)

    for index_name in (
        "ix_users_beta_read_penalty_required_at",
        "ix_users_username",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name=USERS_TABLE)
