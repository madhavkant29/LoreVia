from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps.subscription import require_power, require_pro


@pytest.mark.asyncio
async def test_require_pro_allows_author_access():
    await require_pro(SimpleNamespace(tier="author", created_at=None))


@pytest.mark.asyncio
async def test_require_pro_rejects_non_paid_access():
    with pytest.raises(HTTPException) as exc_info:
        await require_pro(SimpleNamespace(tier="free", created_at=None))

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_power_rejects_author_access():
    with pytest.raises(HTTPException) as exc_info:
        await require_power(SimpleNamespace(tier="author", created_at=None))

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_power_allows_architect_access():
    await require_power(SimpleNamespace(tier="architect", created_at=None))
