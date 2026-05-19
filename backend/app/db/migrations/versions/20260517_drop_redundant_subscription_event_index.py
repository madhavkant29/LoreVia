"""Drop redundant subscription_events source_event_id index.

Revision ID: 20260517_drop_redundant_subscription_event_index
Revises: 20260517_finalize_subscription_events_and_remove_monetization
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260517_drop_redundant_subscription_event_index"
down_revision: str | None = "20260517_finalize_subscription_events_and_remove_monetization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "subscription_events" not in _table_names(inspector):
        return

    indexes = _index_names(inspector, "subscription_events")
    if "ix_subscription_events_source_event_id" in indexes:
        op.drop_index("ix_subscription_events_source_event_id", table_name="subscription_events")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "subscription_events" not in _table_names(inspector):
        return

    indexes = _index_names(inspector, "subscription_events")
    if "ix_subscription_events_source_event_id" not in indexes:
        op.create_index(
            "ix_subscription_events_source_event_id",
            "subscription_events",
            ["source_event_id"],
            unique=False,
        )
