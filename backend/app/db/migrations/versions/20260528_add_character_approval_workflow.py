"""Add character approval workflow fields and decision audit table.

Revision ID: 20260528_add_character_approval_workflow
Revises: 20260527_add_users_supabase_auth_id
Create Date: 2026-05-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260528_add_character_approval_workflow"
down_revision: str | Sequence[str] | None = "20260527_add_users_supabase_auth_id"
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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "characters" not in tables:
        return

    character_columns = _column_names(inspector, "characters")
    if "visibility_state" not in character_columns:
        op.add_column("characters", sa.Column("visibility_state", sa.String(), nullable=False, server_default="visible"))
    if "approval_state" not in character_columns:
        op.add_column("characters", sa.Column("approval_state", sa.String(), nullable=False, server_default="approved"))
    if "approval_source" not in character_columns:
        op.add_column("characters", sa.Column("approval_source", sa.String(), nullable=True))
    if "approval_reason_codes" not in character_columns:
        op.add_column("characters", sa.Column("approval_reason_codes", postgresql.ARRAY(sa.String()), nullable=True))
    if "approval_updated_at" not in character_columns:
        op.add_column("characters", sa.Column("approval_updated_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        sa.text(
            """
            update characters
            set
              visibility_state = case
                when is_manual = true
                  or coalesce(analysis_metadata->>'user_curated', 'false') = 'true'
                  or coalesce(analysis_metadata->>'protected_from_repair', 'false') = 'true'
                  then 'visible'
                when coalesce(analysis_metadata->>'trust_tier', '') = 'review_only'
                  then 'quarantined'
                when coalesce(analysis_metadata->>'trust_tier', '') = 'repaired_noise'
                  then 'noise'
                else coalesce(nullif(visibility_state, ''), 'visible')
              end,
              approval_state = case
                when is_manual = true
                  or coalesce(analysis_metadata->>'user_curated', 'false') = 'true'
                  or coalesce(analysis_metadata->>'protected_from_repair', 'false') = 'true'
                  then 'protected'
                when coalesce(analysis_metadata->>'trust_tier', '') = 'review_only'
                  then 'pending_review'
                when coalesce(analysis_metadata->>'trust_tier', '') = 'repaired_noise'
                  then 'rejected'
                else coalesce(nullif(approval_state, ''), 'approved')
              end,
              approval_source = case
                when is_manual = true
                  or coalesce(analysis_metadata->>'user_curated', 'false') = 'true'
                  or coalesce(analysis_metadata->>'protected_from_repair', 'false') = 'true'
                  then 'manual_review'
                else coalesce(nullif(approval_source, ''), 'legacy_import')
              end,
              approval_updated_at = coalesce(approval_updated_at, now())
            """
        )
    )

    inspector = sa.inspect(bind)
    character_indexes = _index_names(inspector, "characters")
    if "ix_characters_book_visibility_approval" not in character_indexes:
        op.create_index(
            "ix_characters_book_visibility_approval",
            "characters",
            ["book_id", "visibility_state", "approval_state"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_decision_events" not in tables:
        op.create_table(
            "character_decision_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("visibility_state", sa.String(), nullable=True),
            sa.Column("approval_state", sa.String(), nullable=True),
            sa.Column("approval_source", sa.String(), nullable=True),
            sa.Column("reason_codes", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column(
                "evidence",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    decision_indexes = _index_names(inspector, "character_decision_events")
    if "ix_character_decision_events_book_created_at" not in decision_indexes:
        op.create_index(
            "ix_character_decision_events_book_created_at",
            "character_decision_events",
            ["book_id", "created_at"],
            unique=False,
        )
    if "ix_character_decision_events_character_id" not in decision_indexes:
        op.create_index(
            "ix_character_decision_events_character_id",
            "character_decision_events",
            ["character_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "character_decision_events" in tables:
        decision_indexes = _index_names(inspector, "character_decision_events")
        if "ix_character_decision_events_character_id" in decision_indexes:
            op.drop_index("ix_character_decision_events_character_id", table_name="character_decision_events")
        if "ix_character_decision_events_book_created_at" in decision_indexes:
            op.drop_index("ix_character_decision_events_book_created_at", table_name="character_decision_events")
        op.drop_table("character_decision_events")

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "characters" not in tables:
        return
    character_columns = _column_names(inspector, "characters")
    character_indexes = _index_names(inspector, "characters")
    if "ix_characters_book_visibility_approval" in character_indexes:
        op.drop_index("ix_characters_book_visibility_approval", table_name="characters")
    for column_name in (
        "approval_updated_at",
        "approval_reason_codes",
        "approval_source",
        "approval_state",
        "visibility_state",
    ):
        if column_name in character_columns:
            op.drop_column("characters", column_name)
