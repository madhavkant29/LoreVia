"""Align prod schema with current ORM metadata.

Revision ID: 20260516_align_schema_with_models
Revises: 20260516_repair_beta_read_assignment_jsonb_columns
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260516_align_schema_with_models"
down_revision: str | None = "20260516_repair_beta_read_assignment_jsonb_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def _drop_index_if_exists(index_names: dict[str, set[str]], table_name: str, index_name: str) -> None:
    if index_name in index_names.get(table_name, set()):
        op.drop_index(index_name, table_name=table_name)
        index_names[table_name].discard(index_name)


def _drop_unique_constraint_if_exists(
    unique_constraint_names: dict[str, set[str]],
    table_name: str,
    constraint_name: str,
) -> None:
    if constraint_name in unique_constraint_names.get(table_name, set()):
        op.drop_constraint(constraint_name, table_name, type_="unique")
        unique_constraint_names[table_name].discard(constraint_name)


def _create_index_if_missing(
    index_names: dict[str, set[str]],
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if index_name not in index_names.get(table_name, set()):
        op.create_index(index_name, table_name, columns, unique=unique)
        index_names.setdefault(table_name, set()).add(index_name)


def upgrade() -> None:
    for table_name, column_name in (
        ("beta_read_assignments", "author_questions_json"),
        ("beta_read_assignments", "feedback_payload"),
        ("beta_read_assignments", "submission_metadata"),
        ("beta_read_assignments", "metadata_json"),
        ("beta_read_feedback_items", "metadata_json"),
    ):
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = '{table_name}'
                          AND column_name = '{column_name}'
                    ) THEN
                        EXECUTE 'ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP NOT NULL';
                    END IF;
                END
                $$;
                """
            )
        )

    op.execute("CREATE INDEX IF NOT EXISTS \"ix_users_beta_read_penalty_required_at\" ON \"users\" (\"beta_read_penalty_required_at\")")

    for statement in (
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_backlinks_book_id" ON "book_obsidian_note_backlinks" ("book_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_backlinks_created_at" ON "book_obsidian_note_backlinks" ("created_at")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_backlinks_link_type" ON "book_obsidian_note_backlinks" ("link_type")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_backlinks_source_note_id" ON "book_obsidian_note_backlinks" ("source_note_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_backlinks_target_note_id" ON "book_obsidian_note_backlinks" ("target_note_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_backlinks_user_id" ON "book_obsidian_note_backlinks" ("user_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_links_book_id" ON "book_obsidian_note_links" ("book_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_links_created_at" ON "book_obsidian_note_links" ("created_at")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_links_link_type" ON "book_obsidian_note_links" ("link_type")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_links_source_note_id" ON "book_obsidian_note_links" ("source_note_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_links_target_note_id" ON "book_obsidian_note_links" ("target_note_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_links_user_id" ON "book_obsidian_note_links" ("user_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_series_links_created_at" ON "book_obsidian_note_series_links" ("created_at")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_series_links_link_type" ON "book_obsidian_note_series_links" ("link_type")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_series_links_series_id" ON "book_obsidian_note_series_links" ("series_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_series_links_source_book_id" ON "book_obsidian_note_series_links" ("source_book_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_series_links_source_note_id" ON "book_obsidian_note_series_links" ("source_note_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_series_links_target_book_id" ON "book_obsidian_note_series_links" ("target_book_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_series_links_target_note_id" ON "book_obsidian_note_series_links" ("target_note_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_series_links_user_id" ON "book_obsidian_note_series_links" ("user_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_tags_book_id" ON "book_obsidian_note_tags" ("book_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_tags_created_at" ON "book_obsidian_note_tags" ("created_at")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_tags_note_id" ON "book_obsidian_note_tags" ("note_id")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_tags_tag_name" ON "book_obsidian_note_tags" ("tag_name")',
        'CREATE INDEX IF NOT EXISTS "ix_book_obsidian_note_tags_user_id" ON "book_obsidian_note_tags" ("user_id")',
    ):
        op.execute(statement)

    for statement in (
        'DROP INDEX IF EXISTS "ix_chapter_versions_snapshot_kind"',
        'DROP INDEX IF EXISTS "ix_novel_scenes_book_chapter_sort_order"',
        'ALTER TABLE "novel_scenes" DROP CONSTRAINT IF EXISTS "uq_novel_scenes_book_path"',
        'ALTER TABLE "character_voice_profiles" DROP CONSTRAINT IF EXISTS "uq_character_voice_profiles_character_id"',
        'DROP INDEX IF EXISTS "ix_character_voice_profiles_character_id"',
        'CREATE UNIQUE INDEX IF NOT EXISTS "ix_character_voice_profiles_character_id" ON "character_voice_profiles" ("character_id")',
        'ALTER TABLE "referrals" DROP CONSTRAINT IF EXISTS "uq_referrals_referred_user_id"',
        'DROP INDEX IF EXISTS "ix_referrals_referred_user_id"',
        'CREATE UNIQUE INDEX IF NOT EXISTS "ix_referrals_referred_user_id" ON "referrals" ("referred_user_id")',
        'ALTER TABLE "rewarded_ad_sessions" DROP CONSTRAINT IF EXISTS "uq_rewarded_ad_sessions_claim_token"',
        'DROP INDEX IF EXISTS "ix_rewarded_ad_sessions_claim_token"',
        'CREATE UNIQUE INDEX IF NOT EXISTS "ix_rewarded_ad_sessions_claim_token" ON "rewarded_ad_sessions" ("claim_token")',
    ):
        op.execute(statement)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    relevant_tables = {
        "beta_read_assignments",
        "beta_read_feedback_items",
        "users",
        "book_obsidian_note_backlinks",
        "book_obsidian_note_links",
        "book_obsidian_note_series_links",
        "book_obsidian_note_tags",
        "chapter_versions",
        "novel_scenes",
        "character_voice_profiles",
        "referrals",
        "rewarded_ad_sessions",
    }
    index_names = {table: _index_names(inspector, table) for table in tables if table in relevant_tables}

    if "rewarded_ad_sessions" in tables:
        _drop_index_if_exists(index_names, "rewarded_ad_sessions", "ix_rewarded_ad_sessions_claim_token")
        op.create_unique_constraint(
            "uq_rewarded_ad_sessions_claim_token",
            "rewarded_ad_sessions",
            ["claim_token"],
        )
        op.create_index("ix_rewarded_ad_sessions_claim_token", "rewarded_ad_sessions", ["claim_token"])

    if "referrals" in tables:
        _drop_index_if_exists(index_names, "referrals", "ix_referrals_referred_user_id")
        op.create_unique_constraint(
            "uq_referrals_referred_user_id",
            "referrals",
            ["referred_user_id"],
        )
        op.create_index("ix_referrals_referred_user_id", "referrals", ["referred_user_id"])

    if "character_voice_profiles" in tables:
        _drop_index_if_exists(index_names, "character_voice_profiles", "ix_character_voice_profiles_character_id")
        op.create_unique_constraint(
            "uq_character_voice_profiles_character_id",
            "character_voice_profiles",
            ["character_id"],
        )
        op.create_index("ix_character_voice_profiles_character_id", "character_voice_profiles", ["character_id"])

    if "novel_scenes" in tables:
        op.create_unique_constraint("uq_novel_scenes_book_path", "novel_scenes", ["book_id", "path"])
        op.create_index(
            "ix_novel_scenes_book_chapter_sort_order",
            "novel_scenes",
            ["book_id", "chapter_number", "sort_order"],
        )

    if "chapter_versions" in tables:
        op.create_index("ix_chapter_versions_snapshot_kind", "chapter_versions", ["snapshot_kind"])

    if "book_obsidian_note_tags" in tables:
        for index_name in (
            "ix_book_obsidian_note_tags_user_id",
            "ix_book_obsidian_note_tags_tag_name",
            "ix_book_obsidian_note_tags_note_id",
            "ix_book_obsidian_note_tags_created_at",
            "ix_book_obsidian_note_tags_book_id",
        ):
            _drop_index_if_exists(index_names, "book_obsidian_note_tags", index_name)

    if "book_obsidian_note_series_links" in tables:
        for index_name in (
            "ix_book_obsidian_note_series_links_user_id",
            "ix_book_obsidian_note_series_links_target_note_id",
            "ix_book_obsidian_note_series_links_target_book_id",
            "ix_book_obsidian_note_series_links_source_note_id",
            "ix_book_obsidian_note_series_links_source_book_id",
            "ix_book_obsidian_note_series_links_series_id",
            "ix_book_obsidian_note_series_links_link_type",
            "ix_book_obsidian_note_series_links_created_at",
        ):
            _drop_index_if_exists(index_names, "book_obsidian_note_series_links", index_name)

    if "book_obsidian_note_links" in tables:
        for index_name in (
            "ix_book_obsidian_note_links_user_id",
            "ix_book_obsidian_note_links_target_note_id",
            "ix_book_obsidian_note_links_source_note_id",
            "ix_book_obsidian_note_links_link_type",
            "ix_book_obsidian_note_links_created_at",
            "ix_book_obsidian_note_links_book_id",
        ):
            _drop_index_if_exists(index_names, "book_obsidian_note_links", index_name)

    if "book_obsidian_note_backlinks" in tables:
        for index_name in (
            "ix_book_obsidian_note_backlinks_user_id",
            "ix_book_obsidian_note_backlinks_target_note_id",
            "ix_book_obsidian_note_backlinks_source_note_id",
            "ix_book_obsidian_note_backlinks_link_type",
            "ix_book_obsidian_note_backlinks_created_at",
            "ix_book_obsidian_note_backlinks_book_id",
        ):
            _drop_index_if_exists(index_names, "book_obsidian_note_backlinks", index_name)

    if "users" in tables:
        _drop_index_if_exists(index_names, "users", "ix_users_beta_read_penalty_required_at")

    if "beta_read_feedback_items" in tables:
        columns = _column_names(inspector, "beta_read_feedback_items")
        if "metadata_json" in columns:
            op.alter_column(
                "beta_read_feedback_items",
                "metadata_json",
                existing_type=postgresql.JSONB(astext_type=sa.Text()),
                existing_server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            )

    if "beta_read_assignments" in tables:
        columns = _column_names(inspector, "beta_read_assignments")
        jsonb_columns = (
            ("metadata_json", "'{}'::jsonb"),
            ("submission_metadata", "'{}'::jsonb"),
            ("feedback_payload", "'{}'::jsonb"),
            ("author_questions_json", "'[]'::jsonb"),
        )
        for column_name, default_sql in jsonb_columns:
            if column_name in columns:
                op.execute(
                    sa.text(
                        f"UPDATE beta_read_assignments SET {column_name} = {default_sql} WHERE {column_name} IS NULL"
                    )
                )
                op.alter_column(
                    "beta_read_assignments",
                    column_name,
                    existing_type=postgresql.JSONB(astext_type=sa.Text()),
                    existing_server_default=sa.text(default_sql),
                    nullable=False,
                )
