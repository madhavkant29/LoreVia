from __future__ import annotations

import asyncio
import logging
import time

from app.core.config import settings
from app.engine.embeddings.embedder import build_chunk_embedding_text, embed_batch
from app.models.intelligence import BookChunk
from app.parsers.chunker import ChunkingConfig, chunk_text
from app.utils.ingestion_utils import chunked, elapsed_ms

log = logging.getLogger("lorevia.extraction")


async def persist_chapter_chunks_with_embeddings(
    db,
    *,
    book,
    chapter,
    chapter_number: int,
    ch_data: dict,
) -> list[str]:
    chunk_started = time.perf_counter()
    chunks = chunk_text(
        ch_data["text"],
        config=ChunkingConfig(
            target_tokens=settings.CHUNK_TARGET_TOKENS,
            max_tokens=settings.CHUNK_MAX_TOKENS,
            min_tokens=settings.CHUNK_MIN_TOKENS,
            overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
            overlap_ratio=settings.CHUNK_OVERLAP_RATIO,
        ),
    )
    log.info(
        "ingestion_timing stage=chunk book_id=%s chapter=%s elapsed_ms=%s chunks=%s",
        book.id,
        chapter_number,
        elapsed_ms(chunk_started),
        len(chunks),
    )

    embed_started = time.perf_counter()
    chunk_embedding_inputs = [
        build_chunk_embedding_text(
            chapter_number=chapter_number,
            chapter_title=chapter.title or ch_data.get("title"),
            text=chunk,
        )
        for chunk in chunks
    ]
    chunk_batches = chunked(chunk_embedding_inputs, settings.EXTRACTION_EMBED_BATCH_SIZE)
    embed_semaphore = asyncio.Semaphore(
        max(1, min(settings.EXTRACTION_EMBED_CONCURRENCY, len(chunk_batches) or 1))
    )

    async def _embed_with_limit(batch: list[str]) -> list[list[float]]:
        async with embed_semaphore:
            return await embed_batch(
                batch,
                # Provider calls track usage in their own short-lived sessions.
                # Never share the chapter transaction across parallel tasks.
                db=None,
                user_id=book.user_id,
                book_id=book.id,
                feature="chapter_chunk_embedding",
            )

    embed_tasks = [asyncio.create_task(_embed_with_limit(batch)) for batch in chunk_batches]
    try:
        embedded_batches = await asyncio.gather(*embed_tasks)
    except BaseException:
        # asyncio.gather propagates the first error without waiting for sibling
        # tasks. Cancel and drain them before the owning DB session may close.
        for task in embed_tasks:
            task.cancel()
        await asyncio.gather(*embed_tasks, return_exceptions=True)
        raise
    chunk_embeddings = [embedding for batch in embedded_batches for embedding in batch]
    log.info(
        "ingestion_timing stage=embed book_id=%s chapter=%s elapsed_ms=%s batches=%s",
        book.id,
        chapter_number,
        elapsed_ms(embed_started),
        len(chunk_batches),
    )

    for index, (chunk_text_val, emb) in enumerate(zip(chunks, chunk_embeddings)):
        db.add(
            BookChunk(
                book_id=book.id,
                chapter_id=chapter.id,
                chunk_index=index,
                text=chunk_text_val,
                embedding=emb,
                token_count=len(chunk_text_val.split()),
            )
        )

    return chunks
