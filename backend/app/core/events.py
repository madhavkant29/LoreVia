import logging

from sqlalchemy import text

from app.core.database import Base, engine
from app.core.redis import get_redis
from app.db import base  # noqa: F401

log = logging.getLogger("lorevia.startup")


async def on_startup() -> None:
    log.info("LoreVia starting up")
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        # Ensure pgvector extension exists
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight local-schema reconciliation for environments without migrations.
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS total_tokens INTEGER"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS total_chunks INTEGER"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS is_truncated BOOLEAN DEFAULT FALSE NOT NULL"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS mode VARCHAR DEFAULT 'reader' NOT NULL"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS source_kind VARCHAR DEFAULT 'single_upload' NOT NULL"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS cover_s3_key VARCHAR"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS primary_series_id UUID"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS series_name VARCHAR"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS series_order INTEGER"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE NOT NULL"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS public_description VARCHAR"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS copyright_warning BOOLEAN DEFAULT FALSE NOT NULL"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS hidden_at TIMESTAMPTZ"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_books_user_created ON books(user_id, created_at DESC)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_books_user_hidden_created ON books(user_id, hidden_at, created_at DESC)"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS legal_accepted_at TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS legal_version VARCHAR"))
        await conn.execute(text("ALTER TABLE chapters ADD COLUMN IF NOT EXISTS description VARCHAR"))
        await conn.execute(text("ALTER TABLE chapters ADD COLUMN IF NOT EXISTS word_count INTEGER"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chapters_book_number ON chapters(book_id, number)"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chapter_media (
                id UUID PRIMARY KEY,
                book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
                marker VARCHAR NOT NULL,
                asset_type VARCHAR DEFAULT 'image' NOT NULL,
                content_type VARCHAR,
                storage_key VARCHAR NOT NULL,
                caption VARCHAR,
                sort_order INTEGER DEFAULT 0 NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_chapter_media_marker ON chapter_media(chapter_id, marker)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chapter_media_chapter_sort ON chapter_media(chapter_id, sort_order, created_at)"))
        await conn.execute(text("ALTER TABLE reading_progress ADD COLUMN IF NOT EXISTS chapters_read INTEGER[] DEFAULT ARRAY[]::INTEGER[]"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_reading_progress_user_book ON reading_progress(user_id, book_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_characters_book_first_created ON characters(book_id, first_chapter, created_at)"))
        await conn.execute(text("ALTER TABLE characters ADD COLUMN IF NOT EXISTS growth_events JSONB DEFAULT '[]'::jsonb"))
        await conn.execute(text("ALTER TABLE character_states ADD COLUMN IF NOT EXISTS growth_event JSONB"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_character_relationships_book_chapter ON character_relationships(book_id, from_chapter, to_chapter)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_book_chunks_book_chapter_chunk ON book_chunks(book_id, chapter_id, chunk_index)"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_chapter_summaries_chapter_mode ON chapter_summaries(chapter_id, mode)"))
        await conn.execute(text("ALTER TABLE chapter_summaries ADD COLUMN IF NOT EXISTS themes JSONB"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR NOT NULL,
                description VARCHAR,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_series_user_name ON series(user_id, name)"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS series_books (
                id UUID PRIMARY KEY,
                series_id UUID NOT NULL REFERENCES series(id) ON DELETE CASCADE,
                book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                position INTEGER,
                marked_complete BOOLEAN DEFAULT FALSE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_series_books_series_book ON series_books(series_id, book_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_series_books_series_position ON series_books(series_id, position, created_at)"))
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
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quote_entries_user_created ON quote_entries(user_id, created_at DESC)"))
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
