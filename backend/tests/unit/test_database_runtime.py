from app.core.database import _initialize_postgres_session


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.closed = False

    def execute(self, statement: str) -> None:
        self.executed.append(statement)

    def close(self) -> None:
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = _FakeCursor()

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance


def test_initialize_postgres_session_sets_public_search_path() -> None:
    connection = _FakeConnection()

    _initialize_postgres_session(connection)

    assert connection.cursor_instance.executed == ["SET search_path TO public"]
    assert connection.cursor_instance.closed is True


class _NonContextCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.closed = False

    def execute(self, statement: str) -> None:
        self.executed.append(statement)

    def close(self) -> None:
        self.closed = True


class _NonContextConnection:
    def __init__(self) -> None:
        self.cursor_instance = _NonContextCursor()

    def cursor(self) -> _NonContextCursor:
        return self.cursor_instance


def test_initialize_postgres_session_closes_non_context_cursor() -> None:
    connection = _NonContextConnection()

    _initialize_postgres_session(connection)

    assert connection.cursor_instance.executed == ["SET search_path TO public"]
    assert connection.cursor_instance.closed is True
