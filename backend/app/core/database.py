import logging
import time
from collections.abc import AsyncGenerator

from sqlalchemy import event, or_, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, attributes, with_loader_criteria

from app.core.config import settings
from app.utils.observability_metrics import record_db_query

logger = logging.getLogger(__name__)
_last_pool_saturation_warning_at = 0.0
_POOL_SATURATION_WARNING_INTERVAL_SECONDS = 30.0


def _build_engine_config() -> tuple[str, dict]:
    url = make_url(settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"))
    return url.render_as_string(hide_password=False), {"prepare_threshold": None}


def _initialize_postgres_session(dbapi_connection) -> None:
    cursor = dbapi_connection.cursor()
    try:
        # Some psycopg async-adapted cursors do not implement the context
        # manager protocol on the DBAPI wrapper, so close explicitly.
        cursor.execute("SET search_path TO public, extensions")
        cursor.execute(f"SET statement_timeout TO {_effective_statement_timeout_ms()}")
        cursor.execute(
            f"SET idle_in_transaction_session_timeout TO {_effective_idle_transaction_timeout_ms()}"
        )
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()


def _effective_pool_settings() -> tuple[int, int]:
    pool_size = max(1, int(settings.DATABASE_POOL_SIZE))
    max_overflow = max(0, int(settings.DATABASE_MAX_OVERFLOW))
    return pool_size, max_overflow


def _effective_pool_timeout() -> int:
    return max(1, int(settings.DATABASE_POOL_TIMEOUT_SECONDS))


def _effective_statement_timeout_ms() -> int:
    return max(1_000, int(settings.DATABASE_STATEMENT_TIMEOUT_MS))


def _effective_idle_transaction_timeout_ms() -> int:
    return max(1_000, int(settings.DATABASE_IDLE_TRANSACTION_TIMEOUT_MS))


def _safe_pool_metrics(pool) -> dict[str, int]:
    metrics: dict[str, int] = {}
    for label, accessor in (
        ("size", "size"),
        ("checked_out", "checkedout"),
        ("overflow", "overflow"),
    ):
        value = getattr(pool, accessor, None)
        try:
            metrics[label] = int(value()) if callable(value) else int(value)
        except (TypeError, ValueError, AttributeError):
            continue
    return metrics


def _statement_operation(statement: object) -> str:
    normalized = str(statement or "").lstrip()
    if not normalized:
        return "UNKNOWN"
    return normalized.split(None, 1)[0][:24].upper()


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
    pool_timeout=_effective_pool_timeout(),
    pool_pre_ping=True,
    pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
    echo=settings.DATABASE_SQL_ECHO,
    connect_args=engine_connect_args,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_search_path_on_connect(dbapi_connection, _connection_record) -> None:
    _initialize_postgres_session(dbapi_connection)


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _record_query_start(_conn, _cursor, _statement, _parameters, context, _executemany) -> None:
    context._lorevia_query_started_at = time.perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _log_slow_query(_conn, _cursor, statement, _parameters, context, _executemany) -> None:
    started_at = getattr(context, "_lorevia_query_started_at", None)
    if started_at is None:
        return
    elapsed_ms = (time.perf_counter() - started_at) * 1_000
    record_db_query(elapsed_ms)
    if elapsed_ms < int(settings.DATABASE_SLOW_QUERY_LOG_MS):
        return
    logger.warning(
        "Slow database statement",
        extra={
            "db_operation": _statement_operation(statement),
            "duration_ms": round(elapsed_ms, 2),
            "pool": _safe_pool_metrics(engine.sync_engine.pool),
        },
    )


@event.listens_for(engine.sync_engine.pool, "checkout")
def _warn_on_pool_saturation(_dbapi_connection, _connection_record, _connection_proxy) -> None:
    global _last_pool_saturation_warning_at

    metrics = _safe_pool_metrics(engine.sync_engine.pool)
    checked_out = metrics.get("checked_out", 0)
    capacity = engine_pool_size + engine_max_overflow
    warning_threshold = max(1, (capacity * 80 + 99) // 100)
    if checked_out < warning_threshold:
        return

    now = time.monotonic()
    if now - _last_pool_saturation_warning_at < _POOL_SATURATION_WARNING_INTERVAL_SECONDS:
        return
    _last_pool_saturation_warning_at = now
    logger.warning(
        "Database pool is near capacity",
        extra={"pool": metrics, "configured_capacity": capacity},
    )


AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "do_orm_execute")
def _apply_book_generation_visibility(execute_state) -> None:
    """Hide staging/retired derived rows from ordinary ORM operations."""
    if execute_state.execution_options.get("include_all_generations"):
        return
    if not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
        return

    from app.models.generation import BookDataGeneration, GenerationScopedMixin
    from app.services.data_generation_service import current_generation_id

    scoped_generation_id = current_generation_id()
    if scoped_generation_id is not None:
        visibility = with_loader_criteria(
            GenerationScopedMixin,
            lambda entity: or_(
                entity.generation_id.is_(None),
                entity.generation_id == scoped_generation_id,
            ),
            include_aliases=True,
        )
    else:
        active_generation_ids = select(BookDataGeneration.id).where(
            BookDataGeneration.status == "active"
        )
        visibility = with_loader_criteria(
            GenerationScopedMixin,
            lambda entity: or_(
                entity.generation_id.is_(None),
                entity.generation_id.in_(active_generation_ids),
            ),
            include_aliases=True,
        )
    execute_state.statement = execute_state.statement.options(visibility)


@event.listens_for(Session, "before_flush")
def _assign_or_preserve_book_generation(session, _flush_context, _instances) -> None:
    from app.models.character import Character
    from app.models.generation import GenerationScopedMixin
    from app.models.intelligence import CharacterRelationship, PlotThread, WorldElement
    from app.services.data_generation_service import current_generation_id

    scoped_generation_id = current_generation_id()
    for row in session.new:
        if isinstance(row, GenerationScopedMixin) and row.generation_id is None:
            row.generation_id = scoped_generation_id

    for row in session.new.union(session.dirty):
        if not isinstance(row, GenerationScopedMixin):
            continue
        if isinstance(row, Character):
            metadata = row.analysis_metadata if isinstance(row.analysis_metadata, dict) else {}
            is_curated = bool(
                row.is_manual
                or metadata.get("user_curated")
                or metadata.get("protected_from_repair")
                or row.approval_source == "manual_review"
            )
            if is_curated:
                row.generation_id = None
                state = sa_inspect(row)
                if scoped_generation_id is not None and state.persistent:
                    for column_attribute in state.mapper.column_attrs:
                        key = column_attribute.key
                        history = state.attrs[key].history
                        if history.has_changes() and history.deleted:
                            attributes.set_committed_value(row, key, history.deleted[0])
        elif isinstance(row, (CharacterRelationship, PlotThread, WorldElement)):
            if row.edited_by_author:
                row.generation_id = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
