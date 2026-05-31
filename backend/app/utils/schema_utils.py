from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.user import User, UserLoginActivity

AUTH_RUNTIME_COLUMNS: Mapping[str, frozenset[str]] = {
    User.__tablename__: frozenset(User.__table__.columns.keys()),
    UserLoginActivity.__tablename__: frozenset(UserLoginActivity.__table__.columns.keys()),
}


async def assert_auth_schema_compatible(connection: AsyncConnection) -> None:
    """Raise when the deployed schema cannot serve authentication requests."""

    query = text(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN :table_names
        """
    ).bindparams(bindparam("table_names", expanding=True))
    rows = (await connection.execute(query, {"table_names": tuple(AUTH_RUNTIME_COLUMNS)})).all()
    available_columns: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        available_columns.setdefault(str(table_name), set()).add(str(column_name))

    missing_columns = [
        f"{table_name}.{column_name}"
        for table_name, required_columns in AUTH_RUNTIME_COLUMNS.items()
        for column_name in sorted(required_columns - available_columns.get(table_name, set()))
    ]
    if missing_columns:
        raise RuntimeError(
            "Database schema is missing auth runtime columns: "
            + ", ".join(missing_columns)
        )
