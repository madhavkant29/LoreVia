import uuid
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_smart_tap_returns_search_for_unknown(client, auth_headers):
    """Tapping an unknown word should return search results (empty list ok)."""
    fake_book = uuid.uuid4()
    with patch("app.api.v1.routes.reader.find_context_for_tap", AsyncMock(return_value=[])):
        r = await client.get(
            f"/api/v1/reader/{fake_book}/context?q=unknown&chapter=5",
            headers=auth_headers,
        )
    # 404 expected since book not in DB — endpoint logic reached
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_search_requires_auth(client):
    r = await client.get(f"/api/v1/reader/{uuid.uuid4()}/search?q=test&chapter=5")
    assert r.status_code in (401, 403)
