from app.core.database import engine
from app.core.redis import get_redis
from sqlalchemy import text
import logging

log = logging.getLogger("lorevia.startup")


async def on_startup() -> None:
    log.info("LoreVia starting up")
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        # Ensure pgvector extension exists
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        # Lightweight local-schema reconciliation for environments without migrations.
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS total_tokens INTEGER"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS total_chunks INTEGER"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS is_truncated BOOLEAN DEFAULT FALSE NOT NULL"))
        await conn.execute(text("ALTER TABLE reading_progress ADD COLUMN IF NOT EXISTS chapters_read INTEGER[] DEFAULT ARRAY[]::INTEGER[]"))
        await conn.commit()
    r = await get_redis()
    await r.ping()
    log.info("DB + Redis ready")


async def on_shutdown() -> None:
    await engine.dispose()
    log.info("LoreVia shut down")
