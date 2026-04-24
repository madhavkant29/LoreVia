import asyncio
import sys

import pytest
import pytest_asyncio
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
def mock_storage_uploads(monkeypatch):
    """Mock upload functions to avoid S3/local storage errors in all tests."""
    monkeypatch.setattr("app.core.storage.upload_book_bytes", lambda raw, owner, filename: f"uploads/{owner}/{filename}")
    monkeypatch.setattr("app.core.storage.upload_binary", lambda key, raw, content_type=None: key)


@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch):
    """Mock Celery tasks to avoid worker dependency in all tests."""
    class _FakeTask:
        @staticmethod
        def apply_async(*args, **kwargs):
            return None
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _FakeTask())


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Mock Redis to avoid event loop issues with global _redis connection."""
    from app.core import redis as redis_module
    
    class FakeRedis:
        async def ping(self):
            return True
        async def get(self, key):
            return None
        async def set(self, key, value, ex=None, nx=False):
            return True
        async def setex(self, key, ttl, value):
            return True
        async def delete(self, *keys):
            return 0
        async def exists(self, *keys):
            return 0
        async def incr(self, key):
            return 1
        async def pipeline(self, transaction=True):
            class FakePipeline:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                def delete(self, *keys):
                    return self
                def setex(self, key, ttl, value):
                    return self
                async def execute(self):
                    return []
            return FakePipeline()
        async def aclose(self):
            pass
    
    monkeypatch.setattr(redis_module, "_redis", FakeRedis())
    
    async def fake_get_redis():
        return redis_module._redis
    
    monkeypatch.setattr(redis_module, "get_redis", fake_get_redis)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DB = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")
engine_test = None
TestSession = None


@pytest_asyncio.fixture(scope="session")
async def setup_engine():
    global engine_test, TestSession
    engine_test = create_async_engine(TEST_DB, echo=False)
    TestSession = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)
    yield
    await engine_test.dispose()
    engine_test = None
    TestSession = None


@pytest_asyncio.fixture(scope="session")
async def setup_db(setup_engine):
    async with engine_test.begin() as conn:
        # Enable pgvector extension for vector columns
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(setup_db):
    async with TestSession() as s:
        yield s


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
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


@pytest_asyncio.fixture
async def auth_headers(client):
    import uuid
    r = await client.post("/api/v1/auth/register", json={"email": f"user-{uuid.uuid4()}@lorevia.app", "password": "SecurePass456!@#", "accepted_terms": True})
    if r.status_code != 201:
        raise Exception(f"Registration failed: {r.status_code} - {r.text}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
