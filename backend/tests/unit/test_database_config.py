from app.core import database


class _FakeCursor:
    def __init__(self):
        self.statements: list[str] = []
        self.closed = False

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def close(self) -> None:
        self.closed = True


class _FakeConnection:
    def __init__(self):
        self.cursor_instance = _FakeCursor()

    def cursor(self):
        return self.cursor_instance


def test_effective_pool_settings_respects_env_overrides(monkeypatch):
    monkeypatch.setattr("app.core.database.settings.DEBUG", True, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_POOL_SIZE", 10, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_MAX_OVERFLOW", 8, raising=False)

    assert database._effective_pool_settings() == (10, 8)


def test_effective_pool_settings_preserves_explicit_values(monkeypatch):
    monkeypatch.setattr("app.core.database.settings.DEBUG", True, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_POOL_SIZE", 3, raising=False)
    monkeypatch.setattr("app.core.database.settings.DATABASE_MAX_OVERFLOW", 2, raising=False)

    assert database._effective_pool_settings() == (3, 2)


def test_effective_pool_timeout_clamps_to_positive_value(monkeypatch):
    monkeypatch.setattr(
        "app.core.database.settings.DATABASE_POOL_TIMEOUT_SECONDS", 0, raising=False
    )

    assert database._effective_pool_timeout() == 1


def test_postgres_session_sets_search_path_and_bounded_timeouts(monkeypatch):
    connection = _FakeConnection()
    monkeypatch.setattr(database.settings, "DATABASE_STATEMENT_TIMEOUT_MS", 45_000)
    monkeypatch.setattr(database.settings, "DATABASE_IDLE_TRANSACTION_TIMEOUT_MS", 30_000)

    database._initialize_postgres_session(connection)

    assert connection.cursor_instance.statements == [
        "SET search_path TO public, extensions",
        "SET statement_timeout TO 45000",
        "SET idle_in_transaction_session_timeout TO 30000",
    ]
    assert connection.cursor_instance.closed is True


def test_database_timeout_helpers_clamp_unsafe_runtime_values(monkeypatch):
    monkeypatch.setattr(database.settings, "DATABASE_STATEMENT_TIMEOUT_MS", 0)
    monkeypatch.setattr(database.settings, "DATABASE_IDLE_TRANSACTION_TIMEOUT_MS", -1)

    assert database._effective_statement_timeout_ms() == 1_000
    assert database._effective_idle_transaction_timeout_ms() == 1_000


def test_slow_query_metadata_never_contains_sql_text():
    assert database._statement_operation("  select secret_column from users") == "SELECT"
    assert database._statement_operation("") == "UNKNOWN"
