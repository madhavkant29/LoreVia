import pytest
from starlette.responses import Response
from types import SimpleNamespace

from app.core import events
from app.main import _LazyMountedApp, _lazy_api_app, ready


def test_api_app_is_not_built_at_import_time() -> None:
    _lazy_api_app._app = None
    assert _lazy_api_app._app is None


@pytest.mark.asyncio
async def test_on_startup_skips_db_and_redis_checks(monkeypatch) -> None:
    db_called = False
    redis_called = False

    class _FailConnect:
        def __call__(self):
            nonlocal db_called
            db_called = True
            raise AssertionError("startup should not connect to the database")

    async def _fail_get_redis():
        nonlocal redis_called
        redis_called = True
        raise AssertionError("startup should not resolve redis")

    fake_engine = SimpleNamespace(connect=_FailConnect())
    monkeypatch.setattr("app.core.database.engine", fake_engine)
    monkeypatch.setattr("app.core.redis.get_redis", _fail_get_redis)

    await events.on_startup()

    assert db_called is False
    assert redis_called is False


@pytest.mark.asyncio
async def test_on_shutdown_disposes_engine(monkeypatch) -> None:
    disposed = False

    async def _fake_dispose():
        nonlocal disposed
        disposed = True

    fake_engine = SimpleNamespace(dispose=_fake_dispose)
    monkeypatch.setattr("app.core.database.engine", fake_engine)

    await events.on_shutdown()

    assert disposed is True


@pytest.mark.asyncio
async def test_ready_checks_database_and_redis(monkeypatch) -> None:
    db_checked = False
    redis_checked = False

    class _FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, statement):
            nonlocal db_checked
            db_checked = True
            assert str(statement) == "SELECT 1"

    class _FakeEngine:
        def connect(self):
            return _FakeConnection()

    class _FakeRedis:
        async def ping(self):
            nonlocal redis_checked
            redis_checked = True
            return True

    async def _fake_get_redis():
        return _FakeRedis()

    monkeypatch.setattr("app.core.database.engine", _FakeEngine())
    monkeypatch.setattr("app.core.redis.get_redis", _fake_get_redis)

    result = await ready()

    assert result == {"status": "ready"}
    assert db_checked is True
    assert redis_checked is True


@pytest.mark.asyncio
async def test_ready_returns_503_when_dependency_check_fails(monkeypatch) -> None:
    class _BrokenConnection:
        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _BrokenEngine:
        def connect(self):
            return _BrokenConnection()

    monkeypatch.setattr("app.core.database.engine", _BrokenEngine())

    result = await ready()

    assert isinstance(result, Response)
    assert result.status_code == 503
    assert result.body == b"not ready"


@pytest.mark.asyncio
async def test_lazy_mounted_app_defers_factory_until_first_request() -> None:
    built = 0
    called = 0

    async def _fake_app(scope, receive, send):
        nonlocal called
        called += 1
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"ok",
            }
        )

    def _factory():
        nonlocal built
        built += 1
        return _fake_app

    lazy_app = _LazyMountedApp(_factory)

    messages = []

    async def _receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(message):
        messages.append(message)

    scope = {"type": "http", "method": "GET", "path": "/api/v1/test", "headers": []}

    await lazy_app(scope, _receive, _send)
    await lazy_app(scope, _receive, _send)

    assert built == 1
    assert called == 2
    assert messages[0]["status"] == 200
