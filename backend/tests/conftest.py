import asyncio
import sys
import warnings
import weakref

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

warnings.filterwarnings(
    "ignore",
    message=r".*'crypt' is deprecated and slated for removal in Python 3\.13.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyPacked has no __module__ attribute",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyObject has no __module__ attribute",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type swigvarlink has no __module__ attribute",
    category=DeprecationWarning,
)

from app.api.deps.rate_limit import (
    rate_limit_api,
    rate_limit_auth_login,
    rate_limit_auth_password,
    rate_limit_auth_refresh,
    rate_limit_auth_register,
    rate_limit_chat,
    rate_limit_continuity_checker,
    rate_limit_manuscript_import,
    rate_limit_public,
    rate_limit_public_asset,
    rate_limit_recall,
    rate_limit_search,
    rate_limit_summary,
    rate_limit_upload,
    rate_limit_world_building_ai,
    rate_limit_world_building_upload,
)
from app.core.config import allowed_hosts, settings
from app.core.database import Base, get_db
from app.core.storage import download_book
from app.main import app
from app.utils.migration_utils import is_local_database_url


@pytest.fixture(autouse=True)
def test_runtime_defaults(monkeypatch):
    """Run tests with production-like auth and billing behavior by default."""
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(settings, "FREE_MAX_BOOKS", 1, raising=False)
    monkeypatch.setattr(settings, "FREE_TOTAL_TOKEN_BUDGET", 150000, raising=False)
    monkeypatch.setattr(settings, "FREE_SEARCH_PER_DAY", 3, raising=False)
    monkeypatch.setattr(settings, "FREE_SUMMARY_PER_HOUR", 30, raising=False)
    monkeypatch.setattr(settings, "FREE_PREDICTION_PER_DAY", 1, raising=False)
    monkeypatch.setattr(settings, "FREE_RECALL_PER_DAY", 2, raising=False)
    monkeypatch.setattr(settings, "FREE_ADVISOR_PER_DAY", 1, raising=False)
    monkeypatch.setattr(settings, "FREE_ADVISOR_PER_WEEK", 7, raising=False)
    monkeypatch.setattr(settings, "FREE_ADVISOR_PER_MONTH", 30, raising=False)
    monkeypatch.setattr(settings, "FREE_CONTINUITY_PER_DAY", 1, raising=False)


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
def mock_dedup_embeddings(monkeypatch):
    """Keep character dedup embeddings local during tests."""

    async def _fake_embed_for_dedup(name: str, traits: dict) -> list[float]:
        text = f"{name}|{sorted((traits or {}).keys())}"
        seed = sum(ord(char) for char in text)
        return [((seed + index) % 997) / 997 for index in range(1536)]

    async def _fake_find_similar(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.engine.character.deduplicator.embed_for_dedup",
        _fake_embed_for_dedup,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.embed_for_dedup",
        _fake_embed_for_dedup,
        raising=False,
    )
    monkeypatch.setattr(
        "app.engine.character.deduplicator.find_similar",
        _fake_find_similar,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.find_similar",
        _fake_find_similar,
        raising=False,
    )


@pytest.fixture(autouse=True)
def mock_email_delivery(monkeypatch):
    """Prevent tests from consuming Resend quota."""
    def _fake_send(*args, **kwargs):
        return {"id": "test-email-id"}

    monkeypatch.setattr("app.services.email_service._send", lambda payload: True, raising=False)
    monkeypatch.setattr("resend.Emails.send", _fake_send, raising=False)


@pytest.fixture(autouse=True)
def mock_celery_tasks(monkeypatch, request):
    """Mock Celery tasks to avoid worker dependency in all tests."""
    if request.node.module.__name__.endswith("test_extraction_tasks"):
        return

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
def mock_redis(monkeypatch, request):
    """Mock Redis by default while allowing focused runtime tests to opt out."""
    from app.core import redis as redis_module
    from app.api.deps import rate_limit as rate_limit_module

    if request.node.module.__name__.endswith("test_redis_runtime"):
        return

    class FakeRedis:
        def __init__(self):
            self.store: dict[str, str] = {}
            self.sorted_sets: dict[str, dict[str, float]] = {}

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
                def __init__(self):
                    self.ops: list[tuple[str, tuple[object, ...]]] = []

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                def delete(self, *keys):
                    self.ops.append(("delete", keys))
                    return self

                def setex(self, key, ttl, value):
                    self.ops.append(("setex", (key, ttl, value)))
                    return self

                def zremrangebyscore(self, key, minimum, maximum):
                    self.ops.append(("zremrangebyscore", (key, minimum, maximum)))
                    return self

                def zadd(self, key, mapping):
                    self.ops.append(("zadd", (key, mapping)))
                    return self

                def zcard(self, key):
                    self.ops.append(("zcard", (key,)))
                    return self

                def expire(self, key, ttl):
                    self.ops.append(("expire", (key, ttl)))
                    return self

                async def execute(self):
                    results: list[object] = []
                    for op_name, args in self.ops:
                        if op_name == "delete":
                            deleted = 0
                            for key in args:
                                if key in outer.store:
                                    deleted += 1
                                    del outer.store[key]
                                if key in outer.sorted_sets:
                                    deleted += 1
                                    del outer.sorted_sets[key]
                            results.append(deleted)
                        elif op_name == "setex":
                            key, _ttl, value = args
                            outer.store[str(key)] = str(value)
                            results.append(True)
                        elif op_name == "zremrangebyscore":
                            key, minimum, maximum = args
                            entries = outer.sorted_sets.setdefault(str(key), {})
                            removable = [
                                member
                                for member, score in entries.items()
                                if float(minimum) <= score <= float(maximum)
                            ]
                            for member in removable:
                                del entries[member]
                            results.append(len(removable))
                        elif op_name == "zadd":
                            key, mapping = args
                            entries = outer.sorted_sets.setdefault(str(key), {})
                            for member, score in dict(mapping).items():
                                entries[str(member)] = float(score)
                            results.append(len(mapping))
                        elif op_name == "zcard":
                            key = str(args[0])
                            results.append(len(outer.sorted_sets.get(key, {})))
                        elif op_name == "expire":
                            results.append(True)
                    self.ops.clear()
                    return results

            return FakePipeline()

        async def aclose(self):
            pass

    fake_redis = FakeRedis()
    monkeypatch.setattr(redis_module, "_redis_clients", weakref.WeakKeyDictionary(), raising=False)

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_module, "get_redis", fake_get_redis)
    monkeypatch.setattr(rate_limit_module, "get_redis", fake_get_redis)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DB = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")
engine_test = None
TestSession = None


def _test_base_url() -> str:
    hosts = allowed_hosts()
    for preferred in ("localhost", "127.0.0.1"):
        if preferred in hosts:
            return f"http://{preferred}"
    if hosts:
        return f"https://{hosts[0]}"
    return "http://localhost"


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
    app.dependency_overrides[rate_limit_recall] = lambda: None
    app.dependency_overrides[rate_limit_summary] = lambda: None
    app.dependency_overrides[rate_limit_chat] = lambda: None
    app.dependency_overrides[rate_limit_public] = lambda: None
    app.dependency_overrides[rate_limit_public_asset] = lambda: None
    app.dependency_overrides[rate_limit_continuity_checker] = lambda: None
    app.dependency_overrides[rate_limit_upload] = lambda: None
    app.dependency_overrides[rate_limit_manuscript_import] = lambda: None
    app.dependency_overrides[rate_limit_world_building_upload] = lambda: None
    app.dependency_overrides[rate_limit_world_building_ai] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_test_base_url()) as c:
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
