from sqlalchemy import CheckConstraint, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.models.generation import BookDataGeneration
from app.models.intelligence import BookChunk, ChapterSummary
from app.models.operations import ManuscriptImportJob
from app.models.progress import ReadingProgress


def _unique_constraints(table: Table) -> dict[str, tuple[str, ...]]:
    return {
        constraint.name or "": tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_chunk_index_is_unique_within_a_chapter():
    assert _unique_constraints(BookChunk.__table__)[
        "uq_book_chunks_chapter_generation_chunk_index"
    ] == (
        "chapter_id",
        "generation_id",
        "chunk_index",
    )


def test_summary_mode_is_unique_within_a_chapter():
    assert _unique_constraints(ChapterSummary.__table__)[
        "uq_chapter_summaries_chapter_generation_mode"
    ] == ("chapter_id", "generation_id", "mode")


def test_reading_progress_is_unique_for_each_user_and_book():
    assert _unique_constraints(ReadingProgress.__table__)[
        "uq_reading_progress_user_id_book_id"
    ] == ("user_id", "book_id")


def test_manuscript_import_job_schema_uses_jsonb_and_expected_indexes():
    table = ManuscriptImportJob.__table__
    assert set(table.columns) == {
        table.c.id,
        table.c.user_id,
        table.c.book_id,
        table.c.celery_task_id,
        table.c.status,
        table.c.request_json,
        table.c.source_files_json,
        table.c.result_json,
        table.c.error_detail,
        table.c.progress_completed,
        table.c.progress_total,
        table.c.cancel_requested,
        table.c.started_at,
        table.c.completed_at,
        table.c.created_at,
        table.c.updated_at,
    }
    assert isinstance(table.c.request_json.type, JSONB)
    assert isinstance(table.c.source_files_json.type, JSONB)
    assert isinstance(table.c.result_json.type, JSONB)
    assert {index.name for index in table.indexes} == {
        "ix_manuscript_import_jobs_status_created",
        "ix_manuscript_import_jobs_user_updated",
    }
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    } == {"ck_manuscript_import_jobs_status"}


def test_book_data_generation_schema_has_no_duplicate_or_legacy_columns():
    table = BookDataGeneration.__table__
    assert list(table.columns.keys()) == [
        "id",
        "book_id",
        "rebuild_run_id",
        "status",
        "reason",
        "created_at",
        "updated_at",
        "promoted_at",
        "failed_at",
    ]
    assert {index.name for index in table.indexes} == {
        "ix_book_data_generations_book_id",
        "ix_book_data_generations_rebuild_run_id",
        "ix_book_data_generations_status",
        "ix_book_data_generations_status_updated",
        "uq_book_data_generations_active_book",
    }
