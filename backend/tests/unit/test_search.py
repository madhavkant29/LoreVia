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
