from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.release_data_preflight_service import (
    audit_release_data,
    audit_release_data_from_engine,
)


@dataclass
class _MappingRows:
    row: dict[str, int]

    def one(self) -> dict[str, int]:
        return self.row


@dataclass
class _ScalarRows:
    rows: list[str]

    def all(self) -> list[str]:
        return self.rows


class _Result:
    def __init__(
        self,
        *,
        scalar: Any = None,
        mapping: dict[str, int] | None = None,
        scalars: list[str] | None = None,
    ) -> None:
        self._scalar = scalar
        self._mapping = mapping
        self._scalars = scalars

    def scalar_one(self) -> Any:
        return self._scalar

    def mappings(self) -> _MappingRows:
        assert self._mapping is not None
        return _MappingRows(self._mapping)

    def scalars(self) -> _ScalarRows:
        assert self._scalars is not None
        return _ScalarRows(self._scalars)


class _Connection:
    def __init__(
        self,
        *,
        read_only: str = "on",
        duplicates: list[dict[str, int]] | None = None,
        constraints: list[str] | None = None,
        chapter_duplicate_groups: int = 0,
        generation_tables: list[str] | None = None,
    ) -> None:
        self.read_only = read_only
        self.duplicates = list(
            duplicates
            or [
                {"duplicate_groups": 0, "excess_rows": 0},
                {"duplicate_groups": 0, "excess_rows": 0},
                {"duplicate_groups": 0, "excess_rows": 0},
                {"duplicate_groups": 0, "excess_rows": 0},
                {"duplicate_groups": 0, "excess_rows": 0},
                {"duplicate_groups": 0, "excess_rows": 0},
            ]
        )
        self.constraints = constraints or []
        self.chapter_duplicate_groups = chapter_duplicate_groups
        self.generation_tables = (
            generation_tables
            if generation_tables is not None
            else [
                "book_chunks",
                "chapter_summaries",
                "character_aliases",
                "character_duplicate_suggestions",
                "character_voice_profiles",
            ]
        )
        self.statements: list[str] = []

    async def execute(self, statement: Any) -> _Result:
        sql = str(statement)
        self.statements.append(sql)
        if sql == "SET TRANSACTION READ ONLY":
            return _Result()
        if sql == "SHOW transaction_read_only":
            return _Result(scalar=self.read_only)
        if "FROM information_schema.columns" in sql:
            return _Result(scalars=self.generation_tables)
        if "FROM pg_constraint" in sql:
            return _Result(scalars=self.constraints)
        if "FROM chapters" in sql:
            return _Result(scalar=self.chapter_duplicate_groups)
        return _Result(mapping=self.duplicates.pop(0))

    def begin(self) -> _AsyncContext:
        return _AsyncContext(None)


class _AsyncContext:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> Any:
        self.entered = True
        return self.value

    async def __aexit__(self, *_args: Any) -> None:
        self.exited = True


class _Engine:
    def __init__(self, connection: _Connection) -> None:
        self.connection_context = _AsyncContext(connection)

    def connect(self) -> _AsyncContext:
        return self.connection_context


@pytest.mark.asyncio
async def test_release_data_preflight_reports_only_aggregate_duplicate_counts() -> None:
    connection = _Connection(
        duplicates=[
            {"duplicate_groups": 2, "excess_rows": 3},
            {"duplicate_groups": 0, "excess_rows": 0},
            {"duplicate_groups": 0, "excess_rows": 0},
            {"duplicate_groups": 0, "excess_rows": 0},
            {"duplicate_groups": 0, "excess_rows": 0},
            {"duplicate_groups": 1, "excess_rows": 1},
        ],
        constraints=["uq_chapter_summaries_chapter_generation_mode"],
        chapter_duplicate_groups=4,
    )

    result = await audit_release_data(connection)  # type: ignore[arg-type]

    assert result.transaction_read_only is True
    assert result.safe_for_constraint_rollout is False
    assert result.duplicate_checks["book_chunks.chapter_generation_chunk_index"].excess_rows == 3
    assert result.duplicate_checks["reading_progress.user_id_book_id"].duplicate_groups == 1
    assert result.required_constraints_present == ("uq_chapter_summaries_chapter_generation_mode",)
    assert "uq_book_chunks_chapter_generation_chunk_index" in (result.required_constraints_missing)
    assert "uq_reading_progress_user_id_book_id" in result.required_constraints_missing
    assert result.chapter_number_duplicate_groups == 4
    assert result.as_dict()["safe_for_constraint_rollout"] is False
    assert connection.statements[0] == "SET TRANSACTION READ ONLY"
    assert connection.statements[1] == "SHOW transaction_read_only"
    assert any("FROM book_chunks" in statement for statement in connection.statements)
    assert any(
        "GROUP BY chapter_id, generation_id, mode" in statement
        for statement in connection.statements
    )


@pytest.mark.asyncio
async def test_release_data_preflight_marks_clean_data_safe_for_constraint_rollout() -> None:
    connection = _Connection(
        constraints=[
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
        ]
    )

    result = await audit_release_data(connection)  # type: ignore[arg-type]

    assert result.safe_for_constraint_rollout is True
    assert result.required_constraints_missing == ()


@pytest.mark.asyncio
async def test_release_data_preflight_supports_schema_before_generation_migration() -> None:
    connection = _Connection(generation_tables=[])

    result = await audit_release_data(connection)  # type: ignore[arg-type]

    assert result.safe_for_constraint_rollout is True
    assert "book_chunks.chapter_id_chunk_index" in result.duplicate_checks
    assert "chapter_summaries.chapter_id_mode" in result.duplicate_checks
    assert "character_aliases.book_character_alias" in result.duplicate_checks
    assert "character_duplicate_suggestions.book_pair" in result.duplicate_checks
    assert "character_voice_profiles.character_id" in result.duplicate_checks
    assert any(
        "GROUP BY chapter_id, chunk_index" in statement for statement in connection.statements
    )
    assert all(
        "GROUP BY chapter_id, generation_id, chunk_index" not in statement
        for statement in connection.statements
    )


@pytest.mark.asyncio
async def test_release_data_preflight_refuses_a_writable_transaction() -> None:
    connection = _Connection(read_only="off")

    with pytest.raises(RuntimeError, match="read-only transaction"):
        await audit_release_data(connection)  # type: ignore[arg-type]

    assert len(connection.statements) == 2


@pytest.mark.asyncio
async def test_release_data_preflight_from_engine_owns_connection_and_transaction() -> None:
    connection = _Connection()
    engine = _Engine(connection)

    result = await audit_release_data_from_engine(engine)  # type: ignore[arg-type]

    assert result.safe_for_constraint_rollout is True
    assert engine.connection_context.entered is True
    assert engine.connection_context.exited is True
