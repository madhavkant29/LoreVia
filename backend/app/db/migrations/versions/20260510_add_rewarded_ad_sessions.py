"""Add rewarded ad session tracking.

Revision ID: 20260510_add_rewarded_ad_sessions
Revises: 20260507_add_monetization_lifecycle_tables
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260510_add_rewarded_ad_sessions"
down_revision: str | None = "20260507_add_monetization_lifecycle_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    created_table = False
    if "users" in tables and "rewarded_ad_sessions" not in tables:
        op.create_table(
            "rewarded_ad_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("claim_token", sa.String(), nullable=False),
            sa.Column("ad_unit_path", sa.String(), nullable=False),
            sa.Column("placement", sa.String(), nullable=True),
            sa.Column("status", sa.String(), server_default="pending", nullable=False),
            sa.Column("reward_points", sa.Integer(), nullable=False),
            sa.Column("reward_granted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("claim_token", name="uq_rewarded_ad_sessions_claim_token"),
        )
        tables.add("rewarded_ad_sessions")
        created_table = True

    if "users" in tables and "rewarded_ad_sessions" in tables:
        unique_constraints = (
            set()
            if created_table
            else {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("rewarded_ad_sessions")
                if constraint.get("name")
            }
        )
        if "uq_rewarded_ad_sessions_claim_token" not in unique_constraints and not created_table:
            op.create_unique_constraint(
                "uq_rewarded_ad_sessions_claim_token",
                "rewarded_ad_sessions",
                ["claim_token"],
            )

        indexes = _index_names(inspector, "rewarded_ad_sessions")
        for name, columns in (
            ("ix_rewarded_ad_sessions_user_id", ["user_id"]),
            ("ix_rewarded_ad_sessions_provider", ["provider"]),
            ("ix_rewarded_ad_sessions_claim_token", ["claim_token"]),
            ("ix_rewarded_ad_sessions_placement", ["placement"]),
            ("ix_rewarded_ad_sessions_status", ["status"]),
            ("ix_rewarded_ad_sessions_reward_granted_at", ["reward_granted_at"]),
            ("ix_rewarded_ad_sessions_expires_at", ["expires_at"]),
            ("ix_rewarded_ad_sessions_created_at", ["created_at"]),
        ):
            if name not in indexes:
                op.create_index(name, "rewarded_ad_sessions", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rewarded_ad_sessions" in tables:
        op.drop_table("rewarded_ad_sessions")
