"""Read-only Docker Compose Local preflight for backend verification.

Run from the repository root:
    docker compose -f docker-compose-local.yml exec -T api python scripts/preflight_local.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.redis import close_redis, get_redis, get_redis_diagnostics
from app.utils.migration_utils import redact_database_target


async def _database_status() -> dict[str, Any]:
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1),
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None},
    )
    try:
        async with engine.connect() as connection:
            db_ok = (await connection.execute(sa.text("SELECT 1"))).scalar_one() == 1
            vector_version = (
                await connection.execute(
                    sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
            ).scalar_one_or_none()
            alembic_rows = (
                await connection.execute(
                    sa.text(
                        "SELECT version_num FROM alembic_version ORDER BY version_num"
                    )
                )
            ).scalars().all()
            return {
                "ok": db_ok,
                "target": redact_database_target(settings.DATABASE_URL),
                "pgvector": vector_version,
                "alembic_current": list(alembic_rows),
            }
    finally:
        await engine.dispose()


async def _redis_status() -> dict[str, Any]:
    redis = await get_redis()
    try:
        ok = bool(await redis.ping())
        diagnostics = await get_redis_diagnostics()
        diagnostics["ok"] = ok
        return diagnostics
    finally:
        await close_redis()


def _alembic_heads() -> list[str]:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    return sorted(script.get_heads())


async def main() -> int:
    database = await _database_status()
    redis = await _redis_status()
    heads = _alembic_heads()
    report = {
        "database": database,
        "redis": redis,
        "alembic_heads": heads,
        "alembic_at_head": sorted(database["alembic_current"]) == heads,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not database["ok"] or not redis["ok"] or not database["pgvector"]:
        return 1
    return 0 if report["alembic_at_head"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
