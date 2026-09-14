"""Add atomic generations for replaceable book intelligence.

Revision ID: 20260909_book_data_generations
Revises: 20260909_import_jobs_latency

This revision intentionally replaces several legacy unique identities and adds
ON DELETE CASCADE generation foreign keys for machine-derived rows. The upgrade
does not delete application data. The downgrade refuses to proceed when rows
from multiple generations would violate a restored legacy identity; this avoids
silently discarding generation history.

The new table is backend-only and receives no Supabase Data API grants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260909_book_data_generations"
down_revision: str | Sequence[str] | None = "20260909_import_jobs_latency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BATCH_SIZE = 5_000
GENERATION_TABLES = (
    "book_chunks",
    "chapter_summaries",
    "characters",
    "character_aliases",
    "character_states",
    "character_voice_profiles",
    "character_candidates",
    "character_mentions",
    "character_duplicate_suggestions",
    "character_relationship_candidates",
    "character_relationships",
    "plot_threads",
    "wiki_entries",
    "world_elements",
    "world_gap_analyses",
)

LEGACY_IDENTITIES = (
    (
        "character_aliases",
        "uq_character_aliases_book_char_alias",
        ("book_id", "character_id", "normalized_alias"),
    ),
    (
        "character_duplicate_suggestions",
        "uq_character_duplicate_suggestions_pair",
        ("book_id", "primary_character_id", "secondary_character_id"),
    ),
    (
        "character_voice_profiles",
        "uq_character_voice_profiles_character_id",
        ("character_id",),
    ),
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_names() -> set[str]:
    return set(_inspector().get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {
        name
        for index in _inspector().get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def _unique_constraint_names(table_name: str) -> set[str]:
    return {
        name
        for constraint in _inspector().get_unique_constraints(table_name)
        if isinstance(name := constraint.get("name"), str)
    }


def _foreign_keys(table_name: str) -> list[dict[str, object]]:
    return list(_inspector().get_foreign_keys(table_name))


def _identity_names(table_name: str) -> set[str]:
    return _index_names(table_name) | _unique_constraint_names(table_name)


def _create_index_if_missing(
    table_name: str,
    index_name: str,
    columns: tuple[str, ...],
    *,
    unique: bool = False,
    where: str | None = None,
) -> None:
    if index_name in _identity_names(table_name):
        return
    op.create_index(
        index_name,
        table_name,
        list(columns),
        unique=unique,
        postgresql_where=sa.text(where) if where else None,
    )


def _create_unique_constraint_if_missing(
    table_name: str,
    constraint_name: str,
    columns: tuple[str, ...],
) -> None:
    if constraint_name not in _identity_names(table_name):
        op.create_unique_constraint(constraint_name, table_name, list(columns))


def _drop_identity_if_present(table_name: str, identity_name: str) -> None:
    if identity_name in _unique_constraint_names(table_name):
        op.drop_constraint(identity_name, table_name, type_="unique")
    elif identity_name in _index_names(table_name):
        op.drop_index(identity_name, table_name=table_name)


def _generation_fk_names(table_name: str) -> tuple[str, ...]:
    names: list[str] = []
    for foreign_key in _foreign_keys(table_name):
        constrained = tuple(foreign_key.get("constrained_columns") or ())
        referred_table = foreign_key.get("referred_table")
        name = foreign_key.get("name")
        if (
            constrained == ("generation_id",)
            and referred_table == "book_data_generations"
            and isinstance(name, str)
        ):
            names.append(name)
    return tuple(names)


def _duplicate_group_count(table_name: str, columns: tuple[str, ...]) -> int:
    grouped = ", ".join(columns)
    value = op.get_bind().execute(
        sa.text(
            f"""
            SELECT COUNT(*)::bigint
            FROM (
                SELECT 1
                FROM {table_name}
                GROUP BY {grouped}
                HAVING COUNT(*) > 1
            ) AS duplicate_groups
            """
        )
    ).scalar_one()
    return int(value or 0)


def _assert_identity_is_clean(
    table_name: str,
    legacy_columns: tuple[str, ...],
    generation_columns: tuple[str, ...],
) -> None:
    columns = (
        generation_columns
        if "generation_id" in _column_names(table_name)
        else legacy_columns
    )
    if _duplicate_group_count(table_name, columns):
        joined = ", ".join(columns)
        raise RuntimeError(
            f"Refusing generation migration: duplicate {table_name} groups exist for ({joined})."
        )


def _execute_batched_update(statement: str) -> None:
    while True:
        result = op.get_bind().execute(
            sa.text(statement.rstrip() + "\nRETURNING 1"),
            {"batch_size": BATCH_SIZE},
        )
        affected = len(result.fetchall())
        if affected < BATCH_SIZE:
            return


def _backfill_by_book(table_name: str, predicate: str = "TRUE") -> None:
    _execute_batched_update(
        f"""
        WITH batch AS (
            SELECT target.ctid AS target_ctid, generation.id AS generation_id
            FROM {table_name} AS target
            JOIN book_data_generations AS generation
              ON generation.book_id = target.book_id
             AND generation.status = 'active'
            WHERE target.generation_id IS NULL
              AND ({predicate})
            LIMIT :batch_size
        )
        UPDATE {table_name} AS target
        SET generation_id = batch.generation_id
        FROM batch
        WHERE target.ctid = batch.target_ctid
        """
    )


def _count(statement: str) -> int:
    value = op.get_bind().execute(sa.text(statement)).scalar_one()
    return int(value or 0)


def _assert_no_unscoped_rows(table_name: str, predicate: str = "TRUE") -> None:
    if _count(
        f"""
        SELECT COUNT(*)::bigint
        FROM {table_name} AS target
        WHERE target.generation_id IS NULL
          AND ({predicate})
        """
    ):
        raise RuntimeError(
            f"Generation migration left expected generated rows unscoped in {table_name}."
        )


def _create_generation_table() -> None:
    if "book_data_generations" not in _table_names():
        op.create_table(
            "book_data_generations",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("rebuild_run_id", sa.String(length=32), nullable=False),
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'staging'"),
            ),
            sa.Column("reason", sa.String(length=64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["book_id"],
                ["books.id"],
                name="fk_book_data_generations_book_id_books",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_book_data_generations"),
        )

    _create_index_if_missing(
        "book_data_generations",
        "ix_book_data_generations_book_id",
        ("book_id",),
    )
    _create_index_if_missing(
        "book_data_generations",
        "ix_book_data_generations_rebuild_run_id",
        ("rebuild_run_id",),
        unique=True,
    )
    _create_index_if_missing(
        "book_data_generations",
        "ix_book_data_generations_status",
        ("status",),
    )
    _create_index_if_missing(
        "book_data_generations",
        "uq_book_data_generations_active_book",
        ("book_id",),
        unique=True,
        where="status = 'active'",
    )
    _create_index_if_missing(
        "book_data_generations",
        "ix_book_data_generations_status_updated",
        ("status", "updated_at"),
    )


def _add_generation_columns() -> None:
    existing_tables = _table_names()
    missing_tables = sorted(set(GENERATION_TABLES) - existing_tables)
    if missing_tables:
        raise RuntimeError(
            "Refusing generation migration because required tables are missing: "
            + ", ".join(missing_tables)
        )

    for table_name in GENERATION_TABLES:
        if "generation_id" not in _column_names(table_name):
            op.add_column(
                table_name,
                sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
        if not _generation_fk_names(table_name):
            op.create_foreign_key(
                f"fk_{table_name}_generation",
                table_name,
                "book_data_generations",
                ["generation_id"],
                ["id"],
                ondelete="CASCADE",
            )
        _create_index_if_missing(
            table_name,
            f"ix_{table_name}_generation_id",
            ("generation_id",),
        )


def _insert_baseline_generations() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO book_data_generations (
                id,
                book_id,
                rebuild_run_id,
                status,
                reason,
                created_at,
                updated_at,
                promoted_at
            )
            SELECT
                (
                    SUBSTR(seed.value, 1, 8) || '-' ||
                    SUBSTR(seed.value, 9, 4) || '-' ||
                    SUBSTR(seed.value, 13, 4) || '-' ||
                    SUBSTR(seed.value, 17, 4) || '-' ||
                    SUBSTR(seed.value, 21, 12)
                )::uuid,
                book.id,
                MD5('lorevia:migration-baseline-run:' || book.id::text),
                'active',
                'migration_baseline',
                NOW(),
                NOW(),
                NOW()
            FROM books AS book
            CROSS JOIN LATERAL (
                SELECT MD5('lorevia:migration-baseline-id:' || book.id::text) AS value
            ) AS seed
            WHERE NOT EXISTS (
                SELECT 1
                FROM book_data_generations AS existing
                WHERE existing.book_id = book.id
                  AND existing.status = 'active'
            )
            """
        )
    )


CHARACTER_GENERATED_PREDICATE = """
    COALESCE(target.is_manual, FALSE) = FALSE
    AND COALESCE(target.approval_source, '') <> 'manual_review'
    AND LOWER(COALESCE(target.analysis_metadata ->> 'user_curated', 'false'))
        NOT IN ('true', '1', 'yes', 'on')
    AND LOWER(COALESCE(target.analysis_metadata ->> 'protected_from_repair', 'false'))
        NOT IN ('true', '1', 'yes', 'on')
    AND NOT EXISTS (
        SELECT 1
        FROM character_relationships AS relationship
        WHERE relationship.book_id = target.book_id
          AND COALESCE(relationship.edited_by_author, FALSE) = TRUE
          AND (
              relationship.character_a_id = target.id
              OR relationship.character_b_id = target.id
          )
    )
    AND NOT EXISTS (
        SELECT 1
        FROM custom_tags AS tag
        WHERE tag.book_id = target.book_id
          AND tag.entity_type = 'character'
          AND tag.entity_id = target.id
    )
"""


def _backfill_generations() -> None:
    for table_name in (
        "book_chunks",
        "wiki_entries",
        "world_gap_analyses",
        "character_mentions",
        "character_duplicate_suggestions",
        "character_voice_profiles",
    ):
        _backfill_by_book(table_name)

    _execute_batched_update(
        """
        WITH batch AS (
            SELECT target.ctid AS target_ctid, generation.id AS generation_id
            FROM chapter_summaries AS target
            JOIN chapters AS chapter ON chapter.id = target.chapter_id
            JOIN book_data_generations AS generation
              ON generation.book_id = chapter.book_id
             AND generation.status = 'active'
            WHERE target.generation_id IS NULL
            LIMIT :batch_size
        )
        UPDATE chapter_summaries AS target
        SET generation_id = batch.generation_id
        FROM batch
        WHERE target.ctid = batch.target_ctid
        """
    )

    for table_name in ("character_relationships", "plot_threads", "world_elements"):
        _backfill_by_book(
            table_name,
            "COALESCE(target.edited_by_author, FALSE) = FALSE",
        )

    _backfill_by_book("characters", CHARACTER_GENERATED_PREDICATE)

    _execute_batched_update(
        """
        WITH batch AS (
            SELECT target.ctid AS target_ctid, character.generation_id
            FROM character_aliases AS target
            JOIN characters AS character ON character.id = target.character_id
            WHERE target.generation_id IS NULL
              AND character.generation_id IS NOT NULL
            LIMIT :batch_size
        )
        UPDATE character_aliases AS target
        SET generation_id = batch.generation_id
        FROM batch
        WHERE target.ctid = batch.target_ctid
        """
    )

    _execute_batched_update(
        """
        WITH batch AS (
            SELECT target.ctid AS target_ctid, generation.id AS generation_id
            FROM character_states AS target
            JOIN characters AS character ON character.id = target.character_id
            JOIN book_data_generations AS generation
              ON generation.book_id = character.book_id
             AND generation.status = 'active'
            WHERE target.generation_id IS NULL
            LIMIT :batch_size
        )
        UPDATE character_states AS target
        SET generation_id = batch.generation_id
        FROM batch
        WHERE target.ctid = batch.target_ctid
        """
    )

    _execute_batched_update(
        """
        WITH batch AS (
            SELECT target.ctid AS target_ctid, generation.id AS generation_id
            FROM character_candidates AS target
            JOIN book_data_generations AS generation
              ON generation.book_id = target.book_id
             AND generation.status = 'active'
            LEFT JOIN characters AS matched ON matched.id = target.matched_character_id
            WHERE target.generation_id IS NULL
              AND target.status NOT IN ('rejected', 'merged')
              AND target.rejection_reason IS NULL
              AND (
                  target.matched_character_id IS NULL
                  OR matched.generation_id = generation.id
              )
            LIMIT :batch_size
        )
        UPDATE character_candidates AS target
        SET generation_id = batch.generation_id
        FROM batch
        WHERE target.ctid = batch.target_ctid
        """
    )

    _backfill_by_book(
        "character_relationship_candidates",
        "target.status IN ('pending', 'suppressed')",
    )


def _replace_logical_identities() -> None:
    for table_name, identity_name, _columns in LEGACY_IDENTITIES:
        _drop_identity_if_present(table_name, identity_name)
    _drop_identity_if_present("characters", "uq_characters_book_normalized_active")

    _create_unique_constraint_if_missing(
        "book_chunks",
        "uq_book_chunks_chapter_generation_chunk_index",
        ("chapter_id", "generation_id", "chunk_index"),
    )
    _create_index_if_missing(
        "book_chunks",
        "uq_book_chunks_unversioned_chapter_chunk_index",
        ("chapter_id", "chunk_index"),
        unique=True,
        where="generation_id IS NULL",
    )
    _create_unique_constraint_if_missing(
        "chapter_summaries",
        "uq_chapter_summaries_chapter_generation_mode",
        ("chapter_id", "generation_id", "mode"),
    )
    _create_index_if_missing(
        "chapter_summaries",
        "uq_chapter_summaries_unversioned_chapter_mode",
        ("chapter_id", "mode"),
        unique=True,
        where="generation_id IS NULL",
    )
    _create_unique_constraint_if_missing(
        "character_aliases",
        "uq_character_aliases_book_char_generation_alias",
        ("book_id", "character_id", "generation_id", "normalized_alias"),
    )
    _create_index_if_missing(
        "character_aliases",
        "uq_character_aliases_unversioned_book_char_alias",
        ("book_id", "character_id", "normalized_alias"),
        unique=True,
        where="generation_id IS NULL",
    )
    _create_unique_constraint_if_missing(
        "character_duplicate_suggestions",
        "uq_character_duplicate_suggestions_generation_pair",
        (
            "book_id",
            "generation_id",
            "primary_character_id",
            "secondary_character_id",
        ),
    )
    _create_unique_constraint_if_missing(
        "character_voice_profiles",
        "uq_character_voice_profiles_character_generation",
        ("character_id", "generation_id"),
    )
    _create_index_if_missing(
        "character_voice_profiles",
        "uq_character_voice_profiles_unversioned_character",
        ("character_id",),
        unique=True,
        where="generation_id IS NULL",
    )
    _create_index_if_missing(
        "characters",
        "uq_characters_book_generation_normalized_active",
        ("book_id", "generation_id", "normalized_name"),
        unique=True,
        where=(
            "generation_id IS NOT NULL AND normalized_name IS NOT NULL "
            "AND merged_into_character_id IS NULL "
            "AND visibility_state IN ('visible', 'quarantined') "
            "AND approval_state NOT IN ('rejected')"
        ),
    )
    _create_index_if_missing(
        "characters",
        "uq_characters_book_normalized_curated",
        ("book_id", "normalized_name"),
        unique=True,
        where=(
            "generation_id IS NULL AND normalized_name IS NOT NULL "
            "AND merged_into_character_id IS NULL "
            "AND visibility_state IN ('visible', 'quarantined') "
            "AND approval_state NOT IN ('rejected')"
        ),
    )
    _create_unique_constraint_if_missing(
        "reading_progress",
        "uq_reading_progress_user_id_book_id",
        ("user_id", "book_id"),
    )


def _validate_backfill() -> None:
    if _count(
        """
        SELECT COUNT(*)::bigint
        FROM (
            SELECT book.id
            FROM books AS book
            LEFT JOIN book_data_generations AS generation
              ON generation.book_id = book.id
             AND generation.status = 'active'
            GROUP BY book.id
            HAVING COUNT(generation.id) <> 1
        ) AS invalid_books
        """
    ):
        raise RuntimeError("Generation migration did not create exactly one active generation per book.")

    for table_name in (
        "book_chunks",
        "wiki_entries",
        "character_mentions",
        "character_duplicate_suggestions",
        "character_voice_profiles",
    ):
        _assert_no_unscoped_rows(table_name)
    _assert_no_unscoped_rows("world_gap_analyses", "target.book_id IS NOT NULL")
    _assert_no_unscoped_rows(
        "character_relationships",
        "COALESCE(target.edited_by_author, FALSE) = FALSE",
    )
    _assert_no_unscoped_rows(
        "plot_threads",
        "COALESCE(target.edited_by_author, FALSE) = FALSE",
    )
    _assert_no_unscoped_rows(
        "world_elements",
        "COALESCE(target.edited_by_author, FALSE) = FALSE",
    )
    _assert_no_unscoped_rows("characters", CHARACTER_GENERATED_PREDICATE)
    _assert_no_unscoped_rows(
        "character_relationship_candidates",
        "target.status IN ('pending', 'suppressed')",
    )

    if _count(
        """
        SELECT COUNT(*)::bigint
        FROM chapter_summaries AS summary
        JOIN chapters AS chapter ON chapter.id = summary.chapter_id
        WHERE summary.generation_id IS NULL
        """
    ):
        raise RuntimeError("Generation migration left chapter summaries unscoped.")
    if _count(
        """
        SELECT COUNT(*)::bigint
        FROM character_states AS state
        JOIN characters AS character ON character.id = state.character_id
        WHERE state.generation_id IS NULL
        """
    ):
        raise RuntimeError("Generation migration left character states unscoped.")
    if _count(
        """
        SELECT COUNT(*)::bigint
        FROM character_aliases AS alias
        JOIN characters AS character ON character.id = alias.character_id
        WHERE character.generation_id IS NOT NULL
          AND alias.generation_id IS NULL
        """
    ):
        raise RuntimeError("Generation migration left generated character aliases unscoped.")
    if _count(
        """
        SELECT COUNT(*)::bigint
        FROM character_candidates AS candidate
        JOIN book_data_generations AS generation
          ON generation.book_id = candidate.book_id
         AND generation.status = 'active'
        LEFT JOIN characters AS matched ON matched.id = candidate.matched_character_id
        WHERE candidate.generation_id IS NULL
          AND candidate.status NOT IN ('rejected', 'merged')
          AND candidate.rejection_reason IS NULL
          AND (
              candidate.matched_character_id IS NULL
              OR matched.generation_id = generation.id
          )
        """
    ):
        raise RuntimeError("Generation migration left generated character candidates unscoped.")


def upgrade() -> None:
    required_tables = set(GENERATION_TABLES) | {"books", "chapters", "custom_tags", "reading_progress"}
    missing_tables = sorted(required_tables - _table_names())
    if missing_tables:
        raise RuntimeError(
            "Refusing generation migration because required tables are missing: "
            + ", ".join(missing_tables)
        )

    _assert_identity_is_clean(
        "book_chunks",
        ("chapter_id", "chunk_index"),
        ("chapter_id", "generation_id", "chunk_index"),
    )
    _assert_identity_is_clean(
        "chapter_summaries",
        ("chapter_id", "mode"),
        ("chapter_id", "generation_id", "mode"),
    )
    _assert_identity_is_clean(
        "character_aliases",
        ("book_id", "character_id", "normalized_alias"),
        ("book_id", "character_id", "generation_id", "normalized_alias"),
    )
    _assert_identity_is_clean(
        "character_duplicate_suggestions",
        ("book_id", "primary_character_id", "secondary_character_id"),
        (
            "book_id",
            "generation_id",
            "primary_character_id",
            "secondary_character_id",
        ),
    )
    _assert_identity_is_clean(
        "character_voice_profiles",
        ("character_id",),
        ("character_id", "generation_id"),
    )
    _assert_identity_is_clean(
        "reading_progress",
        ("user_id", "book_id"),
        ("user_id", "book_id"),
    )

    _create_generation_table()
    _add_generation_columns()
    _insert_baseline_generations()
    _backfill_generations()
    _replace_logical_identities()
    _validate_backfill()


def _assert_downgrade_is_lossless() -> None:
    checks = (
        (
            "character_aliases",
            ("book_id", "character_id", "normalized_alias"),
        ),
        (
            "character_duplicate_suggestions",
            ("book_id", "primary_character_id", "secondary_character_id"),
        ),
        ("character_voice_profiles", ("character_id",)),
    )
    for table_name, columns in checks:
        if _duplicate_group_count(table_name, columns):
            raise RuntimeError(
                "Refusing generation downgrade because restoring the legacy "
                f"{table_name} identity would require deleting data."
            )

    if _count(
        """
        SELECT COUNT(*)::bigint
        FROM (
            SELECT book_id, normalized_name
            FROM characters
            WHERE normalized_name IS NOT NULL
              AND merged_into_character_id IS NULL
              AND visibility_state IN ('visible', 'quarantined')
              AND approval_state NOT IN ('rejected')
            GROUP BY book_id, normalized_name
            HAVING COUNT(*) > 1
        ) AS duplicate_groups
        """
    ):
        raise RuntimeError(
            "Refusing generation downgrade because restoring the legacy character "
            "identity would require deleting data."
        )


def downgrade() -> None:
    if "book_data_generations" not in _table_names():
        return

    _assert_downgrade_is_lossless()

    new_identities = (
        (
            "book_chunks",
            "uq_book_chunks_chapter_generation_chunk_index",
        ),
        (
            "book_chunks",
            "uq_book_chunks_unversioned_chapter_chunk_index",
        ),
        (
            "chapter_summaries",
            "uq_chapter_summaries_chapter_generation_mode",
        ),
        (
            "chapter_summaries",
            "uq_chapter_summaries_unversioned_chapter_mode",
        ),
        (
            "character_aliases",
            "uq_character_aliases_book_char_generation_alias",
        ),
        (
            "character_aliases",
            "uq_character_aliases_unversioned_book_char_alias",
        ),
        (
            "character_duplicate_suggestions",
            "uq_character_duplicate_suggestions_generation_pair",
        ),
        (
            "character_voice_profiles",
            "uq_character_voice_profiles_character_generation",
        ),
        (
            "character_voice_profiles",
            "uq_character_voice_profiles_unversioned_character",
        ),
        (
            "characters",
            "uq_characters_book_generation_normalized_active",
        ),
        ("characters", "uq_characters_book_normalized_curated"),
        ("reading_progress", "uq_reading_progress_user_id_book_id"),
    )
    for table_name, identity_name in new_identities:
        _drop_identity_if_present(table_name, identity_name)

    for table_name in GENERATION_TABLES:
        if table_name not in _table_names() or "generation_id" not in _column_names(table_name):
            continue
        op.execute(sa.text(f"UPDATE {table_name} SET generation_id = NULL"))
        generation_index = f"ix_{table_name}_generation_id"
        if generation_index in _index_names(table_name):
            op.drop_index(generation_index, table_name=table_name)
        for foreign_key_name in _generation_fk_names(table_name):
            op.drop_constraint(foreign_key_name, table_name, type_="foreignkey")
        op.drop_column(table_name, "generation_id")

    for table_name, identity_name, columns in LEGACY_IDENTITIES:
        _create_unique_constraint_if_missing(table_name, identity_name, columns)
    _create_index_if_missing(
        "characters",
        "uq_characters_book_normalized_active",
        ("book_id", "normalized_name"),
        unique=True,
        where=(
            "normalized_name IS NOT NULL "
            "AND merged_into_character_id IS NULL "
            "AND visibility_state IN ('visible', 'quarantined') "
            "AND approval_state NOT IN ('rejected')"
        ),
    )

    op.drop_table("book_data_generations")
