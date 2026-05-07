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
from app.utils.migration_utils import is_local_database_url


@pytest.fixture(autouse=True)
def mock_download_book(monkeypatch):
    """Mock download_book to avoid S3 errors in all tests."""
    monkeypatch.setattr("app.core.storage.download_book", lambda key: b"mock content")


@pytest.fixture(autouse=True)
def mock_storage_uploads(monkeypatch):
    """Mock upload functions to avoid S3/local storage errors in all tests."""
    # Force local storage mode by mocking S3_ENDPOINT_URL
    monkeypatch.setattr("app.core.config.settings.S3_ENDPOINT_URL", "file://local", raising=False)
    monkeypatch.setattr("app.core.storage.upload_book_bytes", lambda raw, owner, filename: f"uploads/{owner}/{filename}", raising=False)
    monkeypatch.setattr("app.core.storage.upload_binary", lambda key, raw, content_type=None: key, raising=False)
    monkeypatch.setattr("app.core.storage.upload_book", lambda *args, **kwargs: "books/mock.pdf", raising=False)
    monkeypatch.setattr("app.core.storage.upload_text", lambda key, content: key, raising=False)


@pytest.fixture(autouse=True)
def mock_email_delivery(monkeypatch):
    """Prevent tests from consuming Resend quota."""
    def _fake_send(*args, **kwargs):
        return {"id": "test-email-id"}

    monkeypatch.setattr("app.services.email_service._send", lambda payload: True, raising=False)
    monkeypatch.setattr("resend.Emails.send", _fake_send, raising=False)


@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch):
    """Mock Celery tasks to avoid worker dependency in all tests."""
    class _FakeTask:
        @staticmethod
        def apply_async(*args, **kwargs):
            return None
        
        @staticmethod
        def delay(*args, **kwargs):
            return None
    
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _FakeTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task.delay", lambda *args, **kwargs: None, raising=False)


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Mock Redis to avoid event loop issues with global _redis connection."""
    from app.core import redis as redis_module

    class FakeRedis:
        def __init__(self):
            self.store: dict[str, str] = {}

        async def ping(self):
            return True

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, ex=None, nx=False):
            if nx and key in self.store:
                return False
            self.store[key] = str(value)
            return True

        async def setex(self, key, ttl, value):
            self.store[key] = str(value)
            return True

        async def delete(self, *keys):
            deleted = 0
            for key in keys:
                if key in self.store:
                    deleted += 1
                    del self.store[key]
            return deleted

        async def exists(self, *keys):
            return sum(1 for key in keys if key in self.store)

        async def incr(self, key):
            value = int(self.store.get(key, "0")) + 1
            self.store[key] = str(value)
            return value

        def pipeline(self, transaction=True):
            outer = self

            class FakePipeline:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                def delete(self, *keys):
                    for key in keys:
                        outer.store.pop(key, None)
                    return self

                def setex(self, key, ttl, value):
                    outer.store[key] = str(value)
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
    if not is_local_database_url(settings.DATABASE_URL):
        raise RuntimeError(
            "Refusing to reset the test schema against a non-local database URL. "
            "Point DATABASE_URL at a disposable local test database before running tests."
        )

    async with engine_test.begin() as conn:
        # Enable pgvector extension for vector columns
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
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
    from app.core.security import create_access_token
    import uuid
    uid = str(uuid.uuid4())[:8]
    email = f"user-{uid}@lorevia.app"
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"user{uid}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    if r.status_code != 201:
        raise Exception(f"Registration failed: {r.status_code} - {r.text}")
    access_token = create_access_token(str(r.json()["id"]))
    return {"Cookie": f"lorevia_access_token={access_token}"}
