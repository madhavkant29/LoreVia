import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book


@dataclass(frozen=True)
class LibraryAggregateStats:
    total_books_read: int
    total_words_read: int
    total_chapters_tracked: int
    total_token_consumption: int


async def load_library_aggregate_stats(
    db: AsyncSession, user_id: uuid.UUID
) -> LibraryAggregateStats:
    totals = (
        await db.execute(
            select(
                func.coalesce(func.sum(Book.total_chapters), 0),
                func.coalesce(func.sum(Book.total_tokens), 0),
            ).where(Book.user_id == user_id)
        )
    ).one()
    reading = (
        await db.execute(
            text(
                """
                WITH progress AS (
                    SELECT
                        rp.id,
                        rp.book_id,
                        rp.current_chapter,
                        LEAST(GREATEST(COALESCE(rp.scroll_pct, 0), 0), 1) AS scroll_pct,
                        COALESCE(rp.chapters_read, ARRAY[]::integer[]) AS chapters_read,
                        COALESCE(b.total_chapters, 0) AS total_chapters
                    FROM reading_progress rp
                    JOIN books b ON b.id = rp.book_id
                    WHERE rp.user_id = :user_id
                ), read_words AS (
                    SELECT p.id, COALESCE(SUM(c.word_count), 0) AS words
                    FROM progress p
                    LEFT JOIN chapters c
                      ON c.book_id = p.book_id AND c.number = ANY(p.chapters_read)
                    GROUP BY p.id
                ), partial_words AS (
                    SELECT
                        p.id,
                        CASE
                            WHEN p.current_chapter = ANY(p.chapters_read) THEN 0
                            ELSE ROUND(COALESCE(c.word_count, 0) * p.scroll_pct)
                        END AS words
                    FROM progress p
                    LEFT JOIN chapters c
                      ON c.book_id = p.book_id AND c.number = p.current_chapter
                )
                SELECT
                    COUNT(*) FILTER (
                        WHERE p.total_chapters > 0
                          AND cardinality(p.chapters_read) >= p.total_chapters
                    ) AS total_books_read,
                    COALESCE(SUM(rw.words + pw.words), 0) AS total_words_read
                FROM progress p
                JOIN read_words rw ON rw.id = p.id
                JOIN partial_words pw ON pw.id = p.id
                """
            ),
            {"user_id": user_id},
        )
    ).one()

    return LibraryAggregateStats(
        total_books_read=int(reading[0] or 0),
        total_words_read=int(reading[1] or 0),
        total_chapters_tracked=int(totals[0] or 0),
        total_token_consumption=int(totals[1] or 0),
    )
