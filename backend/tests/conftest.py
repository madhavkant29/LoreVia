import asyncio
import sys

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps.rate_limit import (
    rate_limit_api,
    rate_limit_auth_login,
    rate_limit_auth_password,
    rate_limit_auth_refresh,
    rate_limit_auth_register,
    rate_limit_chat,
    rate_limit_continuity_checker,
    rate_limit_public,
    rate_limit_public_asset,
    rate_limit_search,
    rate_limit_summary,
)
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.storage import download_book
from app.main import app


@pytest.fixture(autouse=True)
def mock_download_book(monkeypatch):
    """Mock download_book to avoid S3 errors in all tests."""
    monkeypatch.setattr("app.core.storage.download_book", lambda key: b"mock content")


@pytest.fixture(autouse=True)
async def reset_redis():
    """Reset Redis module-level cache between tests to avoid event loop mismatch."""
    from app.core import redis as redis_module
    redis_module._redis = None
    yield
    if redis_module._redis:
        await redis_module._redis.aclose()
    redis_module._redis = None

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DB = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")
engine_test = None
TestSession = None


@pytest.fixture(scope="session")
async def setup_engine():
    global engine_test, TestSession
    engine_test = create_async_engine(TEST_DB, echo=False)
    TestSession = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)
    yield
    await engine_test.dispose()
    engine_test = None
    TestSession = None


@pytest.fixture
async def setup_db(setup_engine):
    async with engine_test.begin() as conn:
        # Enable pgvector extension for vector columns
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db(setup_db):
    async with TestSession() as s:
        yield s


@pytest.fixture
async def client(db):
    app.dependency_overrides[get_db] = lambda: db
    # Disable rate limiting in tests
    app.dependency_overrides[rate_limit_api] = lambda: None
    app.dependency_overrides[rate_limit_auth_register] = lambda: None
    app.dependency_overrides[rate_limit_auth_login] = lambda: None
    app.dependency_overrides[rate_limit_auth_password] = lambda: None
    app.dependency_overrides[rate_limit_auth_refresh] = lambda: None
    app.dependency_overrides[rate_limit_search] = lambda: None
    app.dependency_overrides[rate_limit_summary] = lambda: None
    app.dependency_overrides[rate_limit_chat] = lambda: None
    app.dependency_overrides[rate_limit_public] = lambda: None
    app.dependency_overrides[rate_limit_public_asset] = lambda: None
    app.dependency_overrides[rate_limit_continuity_checker] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client):
    import uuid
    r = await client.post("/api/v1/auth/register", json={"email": f"user-{uuid.uuid4()}@lorevia.app", "password": "SecurePass456!@#", "accepted_terms": True})
    if r.status_code != 201:
        raise Exception(f"Registration failed: {r.status_code} - {r.text}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
