"""Add character identity cleanup tables and soft-merge fields.

Revision ID: 20260601_add_character_identity_cleanup
Revises: 20260601_add_editor_project_columns
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260601_add_character_identity_cleanup"
down_revision: str | Sequence[str] | None = "20260601_add_editor_project_columns"
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
    constraints = [
        *inspector.get_unique_constraints(table_name),
        *inspector.get_foreign_keys(table_name),
    ]
    return {
        name
        for constraint in constraints
        if isinstance(name := constraint.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "characters" in tables:
        columns = _column_names(inspector, "characters")
        if "normalized_name" not in columns:
            op.add_column("characters", sa.Column("normalized_name", sa.String(), nullable=True))
        if "merged_into_character_id" not in columns:
            op.add_column(
                "characters",
                sa.Column("merged_into_character_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
            op.create_foreign_key(
                "fk_characters_merged_into_character_id",
                "characters",
                "characters",
                ["merged_into_character_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "is_auto_suppressed" not in columns:
            op.add_column(
                "characters",
                sa.Column("is_auto_suppressed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            )
        if "suppression_reason" not in columns:
            op.add_column("characters", sa.Column("suppression_reason", sa.String(), nullable=True))

        op.execute(
            sa.text(
                """
                with normalized as (
                    select
                        id,
                        nullif(
                            trim(
                                regexp_replace(
                                    regexp_replace(lower(name), '(^|\\s)(mr|mrs|ms|miss|dr|sir|lady|lord|prof|professor|capt|captain|commander|master|mistress)\\.?($|\\s)', ' ', 'gi'),
                                    '[^a-z'' -]+',
                                    ' ',
                                    'g'
                                )
                            ),
                            ''
                        ) as normalized
                    from characters
                    where normalized_name is null
                ),
                ranked as (
                    select
                        id,
                        normalized,
                        visibility_state in ('visible', 'quarantined')
                          and approval_state <> 'rejected'
                          and merged_into_character_id is null as active_for_unique_index,
                        row_number() over (
                            partition by
                              case
                                when visibility_state in ('visible', 'quarantined')
                                  and approval_state <> 'rejected'
                                  and merged_into_character_id is null
                                  then book_id
                                else null
                              end,
                              case
                                when visibility_state in ('visible', 'quarantined')
                                  and approval_state <> 'rejected'
                                  and merged_into_character_id is null
                                  then normalized
                                else id::text
                              end
                            order by coalesce(mention_count, 0) desc, created_at asc, id asc
                        ) as duplicate_rank
                    from characters
                    join normalized using (id)
                    where normalized is not null
                )
                update characters
                set normalized_name = case
                    when not ranked.active_for_unique_index or ranked.duplicate_rank = 1 then ranked.normalized
                    else null
                end
                from ranked
                where characters.id = ranked.id
                """
            )
        )

        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "characters")
        if "ix_characters_normalized_name" not in indexes:
            op.create_index("ix_characters_normalized_name", "characters", ["normalized_name"], unique=False)
        if "ix_characters_merged_into_character_id" not in indexes:
            op.create_index("ix_characters_merged_into_character_id", "characters", ["merged_into_character_id"], unique=False)
        if "uq_characters_book_normalized_active" not in indexes:
            op.create_index(
                "uq_characters_book_normalized_active",
                "characters",
                ["book_id", "normalized_name"],
                unique=True,
                postgresql_where=sa.text(
                    "normalized_name is not null and merged_into_character_id is null "
                    "and visibility_state in ('visible', 'quarantined') "
                    "and approval_state not in ('rejected')"
                ),
            )

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_duplicate_suggestions" in tables:
        columns = _column_names(inspector, "character_duplicate_suggestions")
        if "dismissal_reason" not in columns:
            op.add_column("character_duplicate_suggestions", sa.Column("dismissal_reason", sa.String(), nullable=True))
        if "auto_dismissed" not in columns:
            op.add_column(
                "character_duplicate_suggestions",
                sa.Column("auto_dismissed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            )

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_aliases" not in tables:
        op.create_table(
            "character_aliases",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("alias_text", sa.String(), nullable=False),
            sa.Column("normalized_alias", sa.String(), nullable=False),
            sa.Column("alias_kind", sa.String(), nullable=False, server_default="unspecified"),
            sa.Column("source", sa.String(), nullable=False, server_default="extraction"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("book_id", "character_id", "normalized_alias", name="uq_character_aliases_book_char_alias"),
        )
    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "character_aliases")
    if "ix_character_aliases_character_id" not in indexes:
        op.create_index("ix_character_aliases_character_id", "character_aliases", ["character_id"], unique=False)
    if "ix_character_aliases_normalized_alias" not in indexes:
        op.create_index("ix_character_aliases_normalized_alias", "character_aliases", ["normalized_alias"], unique=False)
    if "ix_character_aliases_book_norm_alias" not in indexes:
        op.create_index("ix_character_aliases_book_norm_alias", "character_aliases", ["book_id", "normalized_alias"], unique=False)

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_suppressions" not in tables:
        op.create_table(
            "character_suppressions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("surface_text", sa.String(), nullable=False),
            sa.Column("normalized_text", sa.String(), nullable=False),
            sa.Column("candidate_kind", sa.String(), nullable=True),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("evidence_quote", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "character_suppressions")
    if "ix_character_suppressions_book_id" not in indexes:
        op.create_index("ix_character_suppressions_book_id", "character_suppressions", ["book_id"], unique=False)
    if "ix_character_suppressions_character_id" not in indexes:
        op.create_index("ix_character_suppressions_character_id", "character_suppressions", ["character_id"], unique=False)
    if "ix_character_suppressions_book_normalized_text" not in indexes:
        op.create_index("ix_character_suppressions_book_normalized_text", "character_suppressions", ["book_id", "normalized_text"], unique=False)

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_identity_constraints" not in tables:
        op.create_table(
            "character_identity_constraints",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("left_character_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("right_character_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("left_text", sa.String(), nullable=False),
            sa.Column("right_text", sa.String(), nullable=False),
            sa.Column("constraint_type", sa.String(), nullable=False),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("source", sa.String(), nullable=False, server_default="system"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["left_character_id"], ["characters.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["right_character_id"], ["characters.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("book_id", "left_character_id", "right_character_id", "constraint_type", name="uq_character_identity_constraints"),
        )
    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "character_identity_constraints")
    if "ix_character_identity_constraints_book_id" not in indexes:
        op.create_index("ix_character_identity_constraints_book_id", "character_identity_constraints", ["book_id"], unique=False)
    if "ix_character_identity_constraints_book_type" not in indexes:
        op.create_index("ix_character_identity_constraints_book_type", "character_identity_constraints", ["book_id", "constraint_type"], unique=False)

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "character_identity_actions" not in tables:
        op.create_table(
            "character_identity_actions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("action_type", sa.String(), nullable=False),
            sa.Column("source_character_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("target_character_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("surface_text", sa.String(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("reversible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("reversible_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
            sa.Column("repair_run_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_character_id"], ["characters.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_character_id"], ["characters.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "character_identity_actions")
    if "ix_character_identity_actions_book_id" not in indexes:
        op.create_index("ix_character_identity_actions_book_id", "character_identity_actions", ["book_id"], unique=False)
    if "ix_character_identity_actions_book_created_at" not in indexes:
        op.create_index("ix_character_identity_actions_book_created_at", "character_identity_actions", ["book_id", "created_at"], unique=False)
    if "ix_character_identity_actions_source_character" not in indexes:
        op.create_index("ix_character_identity_actions_source_character", "character_identity_actions", ["source_character_id"], unique=False)
    if "ix_character_identity_actions_target_character" not in indexes:
        op.create_index("ix_character_identity_actions_target_character", "character_identity_actions", ["target_character_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    for table_name, index_names in (
        (
            "character_identity_actions",
            (
                "ix_character_identity_actions_target_character",
                "ix_character_identity_actions_source_character",
                "ix_character_identity_actions_book_created_at",
                "ix_character_identity_actions_book_id",
            ),
        ),
        (
            "character_identity_constraints",
            (
                "ix_character_identity_constraints_book_type",
                "ix_character_identity_constraints_book_id",
            ),
        ),
        (
            "character_suppressions",
            (
                "ix_character_suppressions_book_normalized_text",
                "ix_character_suppressions_character_id",
                "ix_character_suppressions_book_id",
            ),
        ),
        (
            "character_aliases",
            (
                "ix_character_aliases_book_norm_alias",
                "ix_character_aliases_normalized_alias",
                "ix_character_aliases_character_id",
            ),
        ),
    ):
        if table_name not in tables:
            continue
        indexes = _index_names(inspector, table_name)
        for index_name in index_names:
            if index_name in indexes:
                op.drop_index(index_name, table_name=table_name)
        op.drop_table(table_name)
        inspector = sa.inspect(bind)
        tables = _table_names(inspector)

    if "character_duplicate_suggestions" in tables:
        columns = _column_names(inspector, "character_duplicate_suggestions")
        for column_name in ("auto_dismissed", "dismissal_reason"):
            if column_name in columns:
                op.drop_column("character_duplicate_suggestions", column_name)

    if "characters" not in tables:
        return
    indexes = _index_names(inspector, "characters")
    for index_name in (
        "uq_characters_book_normalized_active",
        "ix_characters_merged_into_character_id",
        "ix_characters_normalized_name",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="characters")
    constraints = _constraint_names(inspector, "characters")
    if "fk_characters_merged_into_character_id" in constraints:
        op.drop_constraint("fk_characters_merged_into_character_id", "characters", type_="foreignkey")
    columns = _column_names(inspector, "characters")
    for column_name in (
        "suppression_reason",
        "is_auto_suppressed",
        "merged_into_character_id",
        "normalized_name",
    ):
        if column_name in columns:
            op.drop_column("characters", column_name)
