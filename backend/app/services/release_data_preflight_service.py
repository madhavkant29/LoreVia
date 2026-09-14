from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

REQUIRED_UNIQUE_CONSTRAINTS = frozenset(
    {
        "uq_book_data_generations_active_book",
        "uq_book_chunks_chapter_generation_chunk_index",
        "uq_book_chunks_unversioned_chapter_chunk_index",
        "uq_chapter_summaries_chapter_generation_mode",
        "uq_chapter_summaries_unversioned_chapter_mode",
        "uq_character_aliases_book_char_generation_alias",
        "uq_character_aliases_unversioned_book_char_alias",
        "uq_character_duplicate_suggestions_generation_pair",
        "uq_character_voice_profiles_character_generation",
        "uq_character_voice_profiles_unversioned_character",
        "uq_characters_book_generation_normalized_active",
        "uq_characters_book_normalized_curated",
        "uq_reading_progress_user_id_book_id",
    }
)

_DUPLICATE_CHECKS = (
    (
        "book_chunks.chapter_id_chunk_index",
        "book_chunks.chapter_generation_chunk_index",
        "book_chunks",
        ("chapter_id", "chunk_index"),
        ("chapter_id", "generation_id", "chunk_index"),
    ),
    (
        "chapter_summaries.chapter_id_mode",
        "chapter_summaries.chapter_generation_mode",
        "chapter_summaries",
        ("chapter_id", "mode"),
        ("chapter_id", "generation_id", "mode"),
    ),
    (
        "character_aliases.book_character_alias",
        "character_aliases.book_character_generation_alias",
        "character_aliases",
        ("book_id", "character_id", "normalized_alias"),
        ("book_id", "character_id", "generation_id", "normalized_alias"),
    ),
    (
        "character_duplicate_suggestions.book_pair",
        "character_duplicate_suggestions.generation_pair",
        "character_duplicate_suggestions",
        ("book_id", "primary_character_id", "secondary_character_id"),
        ("book_id", "generation_id", "primary_character_id", "secondary_character_id"),
    ),
    (
        "character_voice_profiles.character_id",
        "character_voice_profiles.character_generation",
        "character_voice_profiles",
        ("character_id",),
        ("character_id", "generation_id"),
    ),
    (
        "reading_progress.user_id_book_id",
        "reading_progress.user_id_book_id",
        "reading_progress",
        ("user_id", "book_id"),
        ("user_id", "book_id"),
    ),
)


@dataclass(frozen=True)
class DuplicateSummary:
    duplicate_groups: int
    excess_rows: int


@dataclass(frozen=True)
class ReleaseDataPreflight:
    transaction_read_only: bool
    duplicate_checks: dict[str, DuplicateSummary]
    required_constraints_present: tuple[str, ...]
    required_constraints_missing: tuple[str, ...]
    chapter_number_duplicate_groups: int
    safe_for_constraint_rollout: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _duplicate_summary_query(table_name: str, columns: tuple[str, ...]) -> str:
    group_columns = ", ".join(columns)
    return f"""
        SELECT
            COUNT(*)::bigint AS duplicate_groups,
            COALESCE(SUM(group_size - 1), 0)::bigint AS excess_rows
        FROM (
            SELECT COUNT(*)::bigint AS group_size
            FROM {table_name}
            GROUP BY {group_columns}
            HAVING COUNT(*) > 1
        ) AS duplicate_groups
    """


async def audit_release_data(connection: AsyncConnection) -> ReleaseDataPreflight:
    """Inspect release-blocking data identities without returning row identifiers or content."""

    await connection.execute(text("SET TRANSACTION READ ONLY"))
    read_only_value = str(
        (await connection.execute(text("SHOW transaction_read_only"))).scalar_one()
    ).casefold()
    transaction_read_only = read_only_value in {"on", "true", "1"}
    if not transaction_read_only:
        raise RuntimeError("Release data preflight requires a read-only transaction.")

    generation_tables = set(
        (
            await connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND column_name = 'generation_id'
                      AND table_name IN (
                          'book_chunks',
                          'chapter_summaries',
                          'character_aliases',
                          'character_duplicate_suggestions',
                          'character_voice_profiles'
                      )
                    """
                )
            )
        )
        .scalars()
        .all()
    )

    duplicate_checks: dict[str, DuplicateSummary] = {}
    for (
        legacy_name,
        generation_name,
        table_name,
        legacy_columns,
        generation_columns,
    ) in _DUPLICATE_CHECKS:
        generation_aware = table_name in generation_tables
        check_name = generation_name if generation_aware else legacy_name
        columns = generation_columns if generation_aware else legacy_columns
        row = (
            (await connection.execute(text(_duplicate_summary_query(table_name, columns))))
            .mappings()
            .one()
        )
        duplicate_checks[check_name] = DuplicateSummary(
            duplicate_groups=int(row["duplicate_groups"] or 0),
            excess_rows=int(row["excess_rows"] or 0),
        )

    constraint_rows = (
        (
            await connection.execute(
                text(
                    """
                SELECT identity_name
                FROM (
                    SELECT conname AS identity_name
                    FROM pg_constraint
                    WHERE connamespace = 'public'::regnamespace
                    UNION
                    SELECT indexname AS identity_name
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                ) AS unique_identities
                WHERE identity_name IN (
                    'uq_book_data_generations_active_book',
                    'uq_book_chunks_chapter_generation_chunk_index',
                    'uq_book_chunks_unversioned_chapter_chunk_index',
                    'uq_chapter_summaries_chapter_generation_mode',
                    'uq_chapter_summaries_unversioned_chapter_mode',
                    'uq_character_aliases_book_char_generation_alias',
                    'uq_character_aliases_unversioned_book_char_alias',
                    'uq_character_duplicate_suggestions_generation_pair',
                    'uq_character_voice_profiles_character_generation',
                    'uq_character_voice_profiles_unversioned_character',
                    'uq_characters_book_generation_normalized_active',
                    'uq_characters_book_normalized_curated',
                    'uq_reading_progress_user_id_book_id'
                )
                ORDER BY identity_name
                """
                )
            )
        )
        .scalars()
        .all()
    )
    constraints_present = tuple(
        sorted(REQUIRED_UNIQUE_CONSTRAINTS.intersection(str(row) for row in constraint_rows))
    )
    constraints_missing = tuple(sorted(REQUIRED_UNIQUE_CONSTRAINTS - set(constraints_present)))

    chapter_number_duplicate_groups = int(
        (
            await connection.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM (
                        SELECT 1
                        FROM chapters
                        GROUP BY book_id, number
                        HAVING COUNT(*) > 1
                    ) AS duplicate_groups
                    """
                )
            )
        ).scalar_one()
        or 0
    )
    safe_for_constraint_rollout = all(
        summary.duplicate_groups == 0 and summary.excess_rows == 0
        for summary in duplicate_checks.values()
    )

    return ReleaseDataPreflight(
        transaction_read_only=transaction_read_only,
        duplicate_checks=duplicate_checks,
        required_constraints_present=constraints_present,
        required_constraints_missing=constraints_missing,
        chapter_number_duplicate_groups=chapter_number_duplicate_groups,
        safe_for_constraint_rollout=safe_for_constraint_rollout,
    )


async def audit_release_data_from_engine(engine: AsyncEngine) -> ReleaseDataPreflight:
    async with engine.connect() as connection:
        async with connection.begin():
            return await audit_release_data(connection)
