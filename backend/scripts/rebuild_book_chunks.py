"""Re-chunk and re-embed stored chapter passages for existing books.

Dry-run by default:
    python scripts/rebuild_book_chunks.py --book-id <uuid>

Apply after review:
    python scripts/rebuild_book_chunks.py --book-id <uuid> --apply --confirm-apply REBUILD_BOOK_CHUNKS
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.storage import download_book
from app.engine.embeddings.embedder import build_chunk_embedding_text, embed_batch
from app.models.book import Book, Chapter
from app.models.intelligence import BookChunk
from app.parsers.chunker import ChunkingConfig, chunk_text
from app.utils.books.manuscript import deserialize_manuscript_content

CONFIRM_TOKEN = "REBUILD_BOOK_CHUNKS"


@dataclass(frozen=True)
class ChapterRebuildPlan:
    chapter_id: str
    chapter_number: int
    chapter_title: str | None
    previous_chunks: int
    next_chunks: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild book chunk rows using the current chunking and embedding format."
    )
    parser.add_argument("--book-id", required=True, help="Target book UUID.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist rebuilt chunks instead of printing a dry-run plan.",
    )
    parser.add_argument(
        "--confirm-apply",
        default="",
        help=f"Required with --apply. Must equal {CONFIRM_TOKEN}.",
    )
    return parser.parse_args()


async def _load_chapter_text(chapter: Chapter) -> str:
    if not chapter.s3_key:
        return ""
    payload = deserialize_manuscript_content(await asyncio.to_thread(download_book, chapter.s3_key))
    return str(payload.get("text") or "")


async def _build_plan(db: AsyncSession, book: Book) -> list[ChapterRebuildPlan]:
    chapters = (
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number)
            )
        )
        .scalars()
        .all()
    )
    plans: list[ChapterRebuildPlan] = []
    chunk_cfg = ChunkingConfig(
        target_tokens=settings.CHUNK_TARGET_TOKENS,
        max_tokens=settings.CHUNK_MAX_TOKENS,
        min_tokens=settings.CHUNK_MIN_TOKENS,
        overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
        overlap_ratio=settings.CHUNK_OVERLAP_RATIO,
    )
    for chapter in chapters:
        text = await _load_chapter_text(chapter)
        existing_count = int(
            await db.scalar(
                select(func.count())
                .select_from(BookChunk)
                .where(BookChunk.chapter_id == chapter.id)
            )
            or 0
        )
        next_chunks = len(chunk_text(text, config=chunk_cfg))
        plans.append(
            ChapterRebuildPlan(
                chapter_id=str(chapter.id),
                chapter_number=int(chapter.number or 0),
                chapter_title=chapter.title,
                previous_chunks=existing_count,
                next_chunks=next_chunks,
            )
        )
    return plans


async def rebuild_book_chunks(*, book_id: uuid.UUID, apply: bool) -> list[ChapterRebuildPlan]:
    async with AsyncSessionLocal() as db:
        book = await db.get(Book, book_id)
        if book is None:
            raise SystemExit(f"Book {book_id} was not found.")

        plans = await _build_plan(db, book)
        if not apply:
            return plans

        chapters = (
            (
                await db.execute(
                    select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number)
                )
            )
            .scalars()
            .all()
        )
        chunk_cfg = ChunkingConfig(
            target_tokens=settings.CHUNK_TARGET_TOKENS,
            max_tokens=settings.CHUNK_MAX_TOKENS,
            min_tokens=settings.CHUNK_MIN_TOKENS,
            overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
            overlap_ratio=settings.CHUNK_OVERLAP_RATIO,
        )

        for chapter in chapters:
            text = await _load_chapter_text(chapter)
            chunks = chunk_text(text, config=chunk_cfg)
            embedding_inputs = [
                build_chunk_embedding_text(
                    chapter_number=chapter.number,
                    chapter_title=chapter.title,
                    text=chunk_text_value,
                )
                for chunk_text_value in chunks
            ]
            embeddings = await embed_batch(
                embedding_inputs,
                db=db,
                user_id=book.user_id,
                book_id=book.id,
                feature="chapter_chunk_embedding_rebuild",
            )

            await db.execute(delete(BookChunk).where(BookChunk.chapter_id == chapter.id))
            for index, (chunk_text_value, embedding) in enumerate(zip(chunks, embeddings)):
                db.add(
                    BookChunk(
                        book_id=book.id,
                        chapter_id=chapter.id,
                        chunk_index=index,
                        text=chunk_text_value,
                        embedding=embedding,
                        token_count=len(chunk_text_value.split()),
                    )
                )

        await db.commit()
        return plans


async def _main() -> None:
    args = _parse_args()
    if args.apply and args.confirm_apply != CONFIRM_TOKEN:
        raise SystemExit(f"--confirm-apply must equal {CONFIRM_TOKEN} when --apply is used.")

    plans = await rebuild_book_chunks(book_id=uuid.UUID(args.book_id), apply=bool(args.apply))
    mode = "applied" if args.apply else "dry-run"
    print(f"Chunk rebuild {mode} for {args.book_id}")
    for plan in plans:
        print(
            f"- Chapter {plan.chapter_number} ({plan.chapter_title or 'Untitled'}): "
            f"{plan.previous_chunks} -> {plan.next_chunks} chunks"
        )


if __name__ == "__main__":
    asyncio.run(_main())
