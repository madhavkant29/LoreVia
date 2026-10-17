import uuid
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.database import (
    _apply_book_generation_visibility,
    _assign_or_preserve_book_generation,
)
from app.models.character import Character
from app.models.generation import BookDataGeneration
from app.models.intelligence import BookChunk, ChapterSummary
from app.services.data_generation_service import current_generation_id, generation_scope


def test_generation_scope_sets_and_restores_context():
    rebuild_run_id = uuid.uuid4().hex

    assert current_generation_id() is None
    with generation_scope(rebuild_run_id) as generation_id:
        assert generation_id == uuid.UUID(rebuild_run_id)
        assert current_generation_id() == generation_id
    assert current_generation_id() is None


def test_generation_scope_restores_context_after_error():
    try:
        with generation_scope(uuid.uuid4().hex):
            raise RuntimeError("provider failed")
    except RuntimeError:
        pass

    assert current_generation_id() is None


def test_replaceable_models_reference_generation_table():
    assert BookDataGeneration.__table__.name == "book_data_generations"
    for model in (BookChunk, ChapterSummary, Character):
        foreign_keys = {
            foreign_key.target_fullname for foreign_key in model.generation_id.foreign_keys
        }
        assert foreign_keys == {"book_data_generations.id"}


def test_new_generated_rows_receive_the_current_generation():
    generation_id = uuid.uuid4()
    session = Session()
    chunk = BookChunk(
        book_id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        chunk_index=0,
        text="Text",
    )
    session.add(chunk)

    with generation_scope(generation_id.hex):
        _assign_or_preserve_book_generation(session, None, None)

    assert chunk.generation_id == generation_id


def test_curated_character_is_removed_from_replaceable_generation():
    session = Session()
    character = Character(
        book_id=uuid.uuid4(),
        name="Mara",
        normalized_name="mara",
        first_chapter=1,
        generation_id=uuid.uuid4(),
        analysis_metadata={"user_curated": True},
    )
    session.add(character)

    _assign_or_preserve_book_generation(session, None, None)

    assert character.generation_id is None


def test_default_query_visibility_includes_only_curated_and_active_rows():
    state = SimpleNamespace(
        execution_options={},
        is_select=True,
        is_update=False,
        is_delete=False,
        statement=select(BookChunk),
    )

    _apply_book_generation_visibility(state)
    sql = str(state.statement.compile(dialect=postgresql.dialect()))

    assert "book_chunks.generation_id IS NULL" in sql
    assert "book_data_generations.status" in sql
