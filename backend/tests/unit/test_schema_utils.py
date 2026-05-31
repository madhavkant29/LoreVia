import pytest

from app.utils.schema_utils import AUTH_RUNTIME_COLUMNS, assert_auth_schema_compatible


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.parameters = None

    async def execute(self, _query, parameters):
        self.parameters = parameters
        return _FakeResult(self.rows)


def _complete_schema_rows():
    return [
        (table_name, column_name)
        for table_name, columns in AUTH_RUNTIME_COLUMNS.items()
        for column_name in columns
    ]


@pytest.mark.asyncio
async def test_assert_auth_schema_compatible_accepts_complete_schema():
    connection = _FakeConnection(_complete_schema_rows())

    await assert_auth_schema_compatible(connection)

    assert set(connection.parameters["table_names"]) == set(AUTH_RUNTIME_COLUMNS)


@pytest.mark.asyncio
async def test_assert_auth_schema_compatible_reports_missing_columns():
    rows = [
        row
        for row in _complete_schema_rows()
        if row not in {("users", "supabase_auth_id"), ("user_login_activity", "login_date")}
    ]

    with pytest.raises(RuntimeError) as exc_info:
        await assert_auth_schema_compatible(_FakeConnection(rows))

    assert "user_login_activity.login_date" in str(exc_info.value)
    assert "users.supabase_auth_id" in str(exc_info.value)
