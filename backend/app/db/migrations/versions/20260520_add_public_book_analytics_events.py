"""Add public book analytics events table.

Revision ID: 20260520_add_public_book_analytics_events
Revises: 20260519_reconcile_social_and_book_schema_drift
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260520_add_public_book_analytics_events"
down_revision: str | None = "20260519_reconcile_social_and_book_schema_drift"
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


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for constraint in inspector.get_unique_constraints(table_name)
        if isinstance(name := constraint.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "public_book_analytics_events" not in tables:
        op.create_table(
            "public_book_analytics_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("visitor_fingerprint_hash", sa.String(), nullable=False),
            sa.Column("event_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "book_id",
                "chapter_number",
                "event_type",
                "visitor_fingerprint_hash",
                "event_date",
                name="uq_public_book_analytics_events_daily_fingerprint",
            ),
        )

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "public_book_analytics_events")
    columns = _column_names(inspector, "public_book_analytics_events")
    unique_constraints = _unique_constraint_names(inspector, "public_book_analytics_events")

    if "uq_public_book_analytics_events_daily_fingerprint" not in unique_constraints and columns:
        op.create_unique_constraint(
            "uq_public_book_analytics_events_daily_fingerprint",
            "public_book_analytics_events",
            ["book_id", "chapter_number", "event_type", "visitor_fingerprint_hash", "event_date"],
        )

    for index_name, column_names in (
        ("ix_public_book_analytics_events_book_created_at", ["book_id", "created_at"]),
        ("ix_public_book_analytics_events_book_event_type", ["book_id", "event_type"]),
        ("ix_public_book_analytics_events_book_event_date", ["book_id", "event_date"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "public_book_analytics_events", column_names)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "public_book_analytics_events" not in tables:
        return

    indexes = _index_names(inspector, "public_book_analytics_events")
    for index_name in (
        "ix_public_book_analytics_events_book_event_date",
        "ix_public_book_analytics_events_book_event_type",
        "ix_public_book_analytics_events_book_created_at",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="public_book_analytics_events")

    op.drop_table("public_book_analytics_events")
