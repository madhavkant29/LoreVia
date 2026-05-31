from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.beta_read import BetaReadAssignment
from app.models.book import Book, BookForumPost, PublicBookAnalyticsEvent, PublicBookRanking
from app.models.intelligence import AdvisorJob
from app.models.user import User, UserLoginActivity

AUTH_RUNTIME_COLUMNS: Mapping[str, frozenset[str]] = {
    User.__tablename__: frozenset(User.__table__.columns.keys()),
    UserLoginActivity.__tablename__: frozenset(UserLoginActivity.__table__.columns.keys()),
}

CORE_RUNTIME_COLUMNS: Mapping[str, frozenset[str]] = {
    **AUTH_RUNTIME_COLUMNS,
    Book.__tablename__: frozenset(Book.__table__.columns.keys()),
    BookForumPost.__tablename__: frozenset(BookForumPost.__table__.columns.keys()),
    PublicBookAnalyticsEvent.__tablename__: frozenset(PublicBookAnalyticsEvent.__table__.columns.keys()),
    PublicBookRanking.__tablename__: frozenset(PublicBookRanking.__table__.columns.keys()),
    BetaReadAssignment.__tablename__: frozenset(BetaReadAssignment.__table__.columns.keys()),
    AdvisorJob.__tablename__: frozenset(AdvisorJob.__table__.columns.keys()),
}


async def _assert_schema_compatible(
    connection: AsyncConnection,
    *,
    required_columns: Mapping[str, frozenset[str]],
    scope_name: str,
) -> None:
    query = text(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN :table_names
        """
    ).bindparams(bindparam("table_names", expanding=True))
    rows = (await connection.execute(query, {"table_names": tuple(required_columns)})).all()
    available_columns: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        available_columns.setdefault(str(table_name), set()).add(str(column_name))

    missing_columns = [
        f"{table_name}.{column_name}"
        for table_name, columns in required_columns.items()
        for column_name in sorted(columns - available_columns.get(table_name, set()))
    ]
    if missing_columns:
        raise RuntimeError(
            f"Database schema is missing {scope_name} runtime columns: "
            + ", ".join(missing_columns)
        )


async def assert_auth_schema_compatible(connection: AsyncConnection) -> None:
    """Raise when the deployed schema cannot serve authentication requests."""

    await _assert_schema_compatible(
        connection,
        required_columns=AUTH_RUNTIME_COLUMNS,
        scope_name="auth",
    )


async def assert_core_runtime_schema_compatible(connection: AsyncConnection) -> None:
    """Raise when the deployed schema cannot serve critical runtime traffic."""

    await _assert_schema_compatible(
        connection,
        required_columns=CORE_RUNTIME_COLUMNS,
        scope_name="core",
    )
