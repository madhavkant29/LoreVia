import logging
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_engine_config() -> tuple[str, dict]:
    url = make_url(settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"))
    return url.render_as_string(hide_password=False), {"prepare_threshold": None}


def _initialize_postgres_session(dbapi_connection) -> None:
    cursor = dbapi_connection.cursor()
    try:
        # Some psycopg async-adapted cursors do not implement the context
        # manager protocol on the DBAPI wrapper, so close explicitly.
        cursor.execute("SET search_path TO public, extensions")
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()


def _effective_pool_settings() -> tuple[int, int]:
    pool_size = max(1, int(settings.DATABASE_POOL_SIZE))
    max_overflow = max(0, int(settings.DATABASE_MAX_OVERFLOW))
    return pool_size, max_overflow


engine_url, engine_connect_args = _build_engine_config()
parsed_engine_url = make_url(engine_url)
engine_pool_size, engine_max_overflow = _effective_pool_settings()

if settings.DEBUG:
    logger.info(
        "Database connection target parsed as user=%s host=%s port=%s database=%s",
        parsed_engine_url.username,
        parsed_engine_url.host,
        parsed_engine_url.port,
        parsed_engine_url.database,
    )


engine = create_async_engine(
    engine_url,
    pool_size=engine_pool_size,
    max_overflow=engine_max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
    echo=settings.DATABASE_SQL_ECHO,
    connect_args=engine_connect_args,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_search_path_on_connect(dbapi_connection, _connection_record) -> None:
    _initialize_postgres_session(dbapi_connection)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
