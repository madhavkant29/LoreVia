"""Add scoped admin principals and admin audit events.

Revision ID: 20260525_add_admin_principals
Revises: 20260524_add_refund_reviews
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260525_add_admin_principals"
down_revision: str | None = "20260524_add_refund_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def _constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for constraint in inspector.get_unique_constraints(table_name)
        if isinstance(name := constraint.get("name"), str)
    }


def _create_index_if_missing(table_name: str, index_name: str, column_names: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    if table_name not in _table_names(inspector):
        return
    columns = _column_names(inspector, table_name)
    indexes = _index_names(inspector, table_name)
    if index_name not in indexes and all(column_name in columns for column_name in column_names):
        op.create_index(index_name, table_name, column_names, unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "admin_principals" not in tables:
        op.create_table(
            "admin_principals",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
            sa.Column("grant_reason", sa.Text(), nullable=False),
            sa.Column("revoke_reason", sa.Text(), nullable=True),
            sa.Column("granted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_admin_principals_user_id"),
        )

    inspector = sa.inspect(bind)
    if "admin_audit_events" not in _table_names(inspector):
        op.create_table(
            "admin_audit_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("target_book_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("target_report_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("target_refund_review_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action_type", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("result", sa.String(), nullable=False),
            sa.Column("request_id", sa.String(), nullable=True),
            sa.Column("ip_address", sa.String(), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("scopes_snapshot", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_book_id"], ["books.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_refund_review_id"], ["refund_reviews.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_report_id"], ["content_reports.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, table_name, column_names in (
        ("ix_admin_principals_user_id", "admin_principals", ["user_id"]),
        ("ix_admin_principals_status", "admin_principals", ["status"]),
        ("ix_admin_principals_is_owner", "admin_principals", ["is_owner"]),
        ("ix_admin_principals_granted_by_user_id", "admin_principals", ["granted_by_user_id"]),
        ("ix_admin_principals_revoked_by_user_id", "admin_principals", ["revoked_by_user_id"]),
        ("ix_admin_principals_created_at", "admin_principals", ["created_at"]),
        ("ix_admin_principals_updated_at", "admin_principals", ["updated_at"]),
        ("ix_admin_principals_revoked_at", "admin_principals", ["revoked_at"]),
        ("ix_admin_audit_events_actor_user_id", "admin_audit_events", ["actor_user_id"]),
        ("ix_admin_audit_events_target_user_id", "admin_audit_events", ["target_user_id"]),
        ("ix_admin_audit_events_target_book_id", "admin_audit_events", ["target_book_id"]),
        ("ix_admin_audit_events_target_report_id", "admin_audit_events", ["target_report_id"]),
        ("ix_admin_audit_events_target_refund_review_id", "admin_audit_events", ["target_refund_review_id"]),
        ("ix_admin_audit_events_action_type", "admin_audit_events", ["action_type"]),
        ("ix_admin_audit_events_result", "admin_audit_events", ["result"]),
        ("ix_admin_audit_events_request_id", "admin_audit_events", ["request_id"]),
        ("ix_admin_audit_events_created_at", "admin_audit_events", ["created_at"]),
    ):
        _create_index_if_missing(table_name, index_name, column_names)

    inspector = sa.inspect(bind)
    if (
        "admin_principals" in _table_names(inspector)
        and "uq_admin_principals_user_id" not in _constraint_names(inspector, "admin_principals")
    ):
        op.create_unique_constraint("uq_admin_principals_user_id", "admin_principals", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    for table_name, index_names in (
        (
            "admin_audit_events",
            (
                "ix_admin_audit_events_created_at",
                "ix_admin_audit_events_request_id",
                "ix_admin_audit_events_result",
                "ix_admin_audit_events_action_type",
                "ix_admin_audit_events_target_refund_review_id",
                "ix_admin_audit_events_target_report_id",
                "ix_admin_audit_events_target_book_id",
                "ix_admin_audit_events_target_user_id",
                "ix_admin_audit_events_actor_user_id",
            ),
        ),
        (
            "admin_principals",
            (
                "ix_admin_principals_revoked_at",
                "ix_admin_principals_updated_at",
                "ix_admin_principals_created_at",
                "ix_admin_principals_revoked_by_user_id",
                "ix_admin_principals_granted_by_user_id",
                "ix_admin_principals_is_owner",
                "ix_admin_principals_status",
                "ix_admin_principals_user_id",
            ),
        ),
    ):
        if table_name not in tables:
            continue
        indexes = _index_names(inspector, table_name)
        for index_name in index_names:
            if index_name in indexes:
                op.drop_index(index_name, table_name=table_name)

    if "admin_audit_events" in tables:
        op.drop_table("admin_audit_events")
    if "admin_principals" in tables:
        op.drop_table("admin_principals")
