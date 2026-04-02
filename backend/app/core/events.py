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
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS series_name VARCHAR"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS series_order INTEGER"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE NOT NULL"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS public_description VARCHAR"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS copyright_warning BOOLEAN DEFAULT FALSE NOT NULL"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS hidden_at TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE chapters ADD COLUMN IF NOT EXISTS description VARCHAR"))
        await conn.execute(text("ALTER TABLE reading_progress ADD COLUMN IF NOT EXISTS chapters_read INTEGER[] DEFAULT ARRAY[]::INTEGER[]"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS quote_entries (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                chapter_number INTEGER,
                character_name VARCHAR,
                quote_text TEXT NOT NULL,
                note VARCHAR,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_rate_limit_overrides (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                search_per_hour INTEGER,
                summary_per_hour INTEGER,
                chat_per_day INTEGER,
                api_per_minute INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS paddle_customer_id VARCHAR"))
        await conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS paddle_sub_id VARCHAR"))
        await conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS paddle_transaction_id VARCHAR"))
        await conn.commit()
    r = await get_redis()
    await r.ping()
    log.info("DB + Redis ready")


async def on_shutdown() -> None:
    await engine.dispose()
    log.info("LoreVia shut down")
