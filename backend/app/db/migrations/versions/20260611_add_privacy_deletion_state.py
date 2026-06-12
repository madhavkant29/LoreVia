"""Add privacy deletion state.

Revision ID: 20260611_privacy_deletion_state
Revises: 20260611_complex_relationship_labels
Create Date: 2026-06-11 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260611_privacy_deletion_state"
down_revision: str | Sequence[str] | None = "20260611_complex_relationship_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


USERS_TABLE = "users"
REQUESTS_TABLE = "data_deletion_requests"


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if USERS_TABLE in tables:
        columns = {column["name"] for column in inspector.get_columns(USERS_TABLE)}
        if "deletion_status" not in columns:
            op.add_column(
                USERS_TABLE,
                sa.Column("deletion_status", sa.String(), nullable=False, server_default="active"),
            )
        if "deletion_requested_at" not in columns:
            op.add_column(USERS_TABLE, sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))
        if "deletion_scheduled_for" not in columns:
            op.add_column(USERS_TABLE, sa.Column("deletion_scheduled_for", sa.DateTime(timezone=True), nullable=True))
        if "deleted_at" not in columns:
            op.add_column(USERS_TABLE, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        if "deleted_email_hash" not in columns:
            op.add_column(USERS_TABLE, sa.Column("deleted_email_hash", sa.String(), nullable=True))
        if "deletion_provider_status" not in columns:
            op.add_column(USERS_TABLE, sa.Column("deletion_provider_status", sa.String(), nullable=True))
        if "deletion_provider_metadata_json" not in columns:
            op.add_column(
                USERS_TABLE,
                sa.Column(
                    "deletion_provider_metadata_json",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False,
                    server_default="{}",
                ),
            )

        indexes = _index_names(inspector, USERS_TABLE)
        for index_name, column_name in (
            ("ix_users_deletion_status", "deletion_status"),
            ("ix_users_deletion_requested_at", "deletion_requested_at"),
            ("ix_users_deletion_scheduled_for", "deletion_scheduled_for"),
            ("ix_users_deleted_at", "deleted_at"),
            ("ix_users_deleted_email_hash", "deleted_email_hash"),
            ("ix_users_deletion_provider_status", "deletion_provider_status"),
        ):
            if index_name not in indexes:
                op.create_index(index_name, USERS_TABLE, [column_name])

    if REQUESTS_TABLE not in tables:
        op.create_table(
            REQUESTS_TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("request_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
            sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("storage_keys_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("provider_actions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if REQUESTS_TABLE in set(inspector.get_table_names()):
        indexes = _index_names(inspector, REQUESTS_TABLE)
        for index_name, column_names in (
            ("ix_data_deletion_requests_user_id", ["user_id"]),
            ("ix_data_deletion_requests_book_id", ["book_id"]),
            ("ix_data_deletion_requests_request_type", ["request_type"]),
            ("ix_data_deletion_requests_status", ["status"]),
            ("ix_data_deletion_requests_scheduled_for", ["scheduled_for"]),
            ("ix_data_deletion_requests_requested_at", ["requested_at"]),
            ("ix_data_deletion_requests_started_at", ["started_at"]),
            ("ix_data_deletion_requests_completed_at", ["completed_at"]),
            ("ix_data_deletion_requests_status_scheduled_for", ["status", "scheduled_for"]),
        ):
            if index_name not in indexes:
                op.create_index(index_name, REQUESTS_TABLE, column_names)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if REQUESTS_TABLE in tables:
        op.drop_table(REQUESTS_TABLE)

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if USERS_TABLE not in tables:
        return

    indexes = _index_names(inspector, USERS_TABLE)
    for index_name in (
        "ix_users_deletion_provider_status",
        "ix_users_deleted_email_hash",
        "ix_users_deleted_at",
        "ix_users_deletion_scheduled_for",
        "ix_users_deletion_requested_at",
        "ix_users_deletion_status",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name=USERS_TABLE)

    columns = {column["name"] for column in inspector.get_columns(USERS_TABLE)}
    for column_name in (
        "deletion_provider_metadata_json",
        "deletion_provider_status",
        "deleted_email_hash",
        "deleted_at",
        "deletion_scheduled_for",
        "deletion_requested_at",
        "deletion_status",
    ):
        if column_name in columns:
            op.drop_column(USERS_TABLE, column_name)
