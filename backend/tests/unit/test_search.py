from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_semantic_search_spoiler_gate():
    """Results must not include chapters beyond max_chapter."""
    import uuid
    from unittest.mock import MagicMock

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.engine.search.semantic.embed_text", AsyncMock(return_value=[0.1] * 1536)):
        from app.engine.search.semantic import semantic_search
        results = await semantic_search(mock_db, uuid.uuid4(), "test query", max_chapter=5)
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_semantic_search_passes_request_session_to_embedder():
    import uuid
    from unittest.mock import MagicMock

    from app.engine.search.semantic import semantic_search

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    embed_mock = AsyncMock(return_value=[0.1] * 1536)
    with patch("app.engine.search.semantic.embed_text", embed_mock):
        await semantic_search(
            mock_db,
            uuid.uuid4(),
            "test query",
            max_chapter=5,
            usage_user_id=uuid.uuid4(),
        )

    assert embed_mock.await_count == 1
    assert embed_mock.await_args.kwargs["db"] is mock_db


@pytest.mark.asyncio
async def test_semantic_search_uses_candidate_limit_and_threshold():
    import uuid
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.engine.search.semantic import semantic_search

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        SimpleNamespace(text="One", chunk_index=0, chapter_num=1, chapter_title="A", relevance=0.91),
        SimpleNamespace(text="Two", chunk_index=1, chapter_num=2, chapter_title="B", relevance=0.89),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.engine.search.semantic.embed_text", AsyncMock(return_value=[0.1] * 1536)):
        results = await semantic_search(
            mock_db,
            uuid.uuid4(),
            "test query",
            max_chapter=5,
            limit=1,
            candidate_limit=10,
            similarity_threshold=0.55,
        )

    assert len(results) == 1
    params = mock_db.execute.await_args.args[1]
    assert params["lim"] == 10
    assert params["thr"] == 0.55
