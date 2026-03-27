"""
Full book processing: parse → chunk → extract characters + relationships → embed.
Lazy: first N chapters immediately, rest queued.
"""
import asyncio
import uuid
from app.core.database import AsyncSessionLocal
from app.core.storage import download_book
from app.core.config import settings
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState
from app.models.intelligence import BookChunk, CharacterRelationship
from app.engine.character.extractor import extract_characters_and_relationships
from app.engine.character.deduplicator import embed_for_dedup, find_similar, merge_alias
from app.engine.character.profile_builder import build_character_profile, update_profile, merge_trait_states
from app.engine.embeddings.embedder import embed_batch, embed_character
from app.parsers.chunker import chunk_text
from sqlalchemy import update as sa_update, select
import logging

log = logging.getLogger("lorevia.extraction")


async def process_book(book_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        book = await db.get(Book, uuid.UUID(book_id))
        if not book:
            return {"error": "not found"}

        await db.execute(sa_update(Book).where(Book.id == book.id).values(status="processing"))
        await db.commit()

        raw = download_book(book.s3_key)
        if book.format == "pdf":
            from app.parsers.pdf_parser import parse_pdf
            chapters = parse_pdf(raw)
        else:
            from app.parsers.epub_parser import parse_epub
            chapters = parse_epub(raw)

        await db.execute(sa_update(Book).where(Book.id == book.id).values(total_chapters=len(chapters)))
        await db.commit()

        # Process first N chapters immediately
        for ch_data in chapters[:settings.LAZY_PROCESS_INITIAL_CHAPTERS]:
            await _process_chapter(db, book, ch_data)

        # Queue the rest
        from app.workers.tasks.extraction_tasks import process_chapter_task
        for ch_data in chapters[settings.LAZY_PROCESS_INITIAL_CHAPTERS:]:
            process_chapter_task.apply_async(
                args=[book_id, ch_data["number"], ch_data["title"], ch_data["text"]],
                countdown=ch_data["number"] * 5,
                queue="extraction",
            )

        await db.execute(sa_update(Book).where(Book.id == book.id).values(status="ready"))
        await db.commit()

        # Queue analysis for processed chapters
        from app.workers.tasks.analysis_tasks import analyse_chapter_task
        for ch_data in chapters[:settings.LAZY_PROCESS_INITIAL_CHAPTERS]:
            ch_obj = (await db.execute(
                select(Chapter).where(Chapter.book_id == book.id, Chapter.number == ch_data["number"])
            )).scalar()
            if ch_obj:
                analyse_chapter_task.apply_async(
                    args=[str(ch_obj.id), ch_data["text"], ch_data["title"]],
                    queue="analysis",
                )

        log.info(f"Book {book_id} processed: {len(chapters)} chapters")
        return {"book_id": book_id, "chapters": len(chapters)}


async def _process_chapter(db, book, ch_data: dict):
    """Extract characters, relationships, store chunks for one chapter."""
    # Store chapter row + raw text in storage
    from app.core.storage import upload_text

    s3_key = f"chapters/{book.id}/{ch_data['number']}.txt"
    try:
        upload_text(s3_key, ch_data["text"])
    except Exception:
        s3_key = ""

    chapter = Chapter(
        book_id=book.id,
        number=ch_data["number"],
        title=ch_data.get("title"),
        s3_key=s3_key,
        processed=True,
    )
    db.add(chapter)
    await db.flush()

    # Chunk + extract
    chunks = chunk_text(ch_data["text"], settings.CHUNK_MAX_TOKENS, settings.CHUNK_OVERLAP_TOKENS)

    # Batch embed all chunks at once — cheaper
    chunk_embeddings = await embed_batch(chunks)

    for i, (chunk_text_val, emb) in enumerate(zip(chunks, chunk_embeddings)):
        chunk_row = BookChunk(
            book_id=book.id,
            chapter_id=chapter.id,
            chunk_index=i,
            text=chunk_text_val,
            embedding=emb,
            token_count=len(chunk_text_val.split()),
        )
        db.add(chunk_row)

    # Extract entities
    for chunk_text_val in chunks:
        result = await extract_characters_and_relationships(chunk_text_val)

        for entity in result["characters"]:
            if not entity.get("name"):
                continue
            emb = await embed_for_dedup(entity["name"], entity.get("traits", {}))
            existing_id = await find_similar(db, book.id, emb, settings.DEDUP_SIMILARITY_THRESHOLD)

            if existing_id:
                char = await db.get(Character, existing_id)
                if char:
                    updated = update_profile(char.trait_state or {}, entity.get("traits", {}), entity.get("archetype"))
                    changed = _changed(char.trait_state or {}, updated["trait_state"])
                    await db.execute(
                        sa_update(Character).where(Character.id == existing_id).values(**updated)
                    )
                    if changed:
                        snap = CharacterState(
                            character_id=existing_id,
                            at_chapter=ch_data["number"],
                            trait_snapshot=updated["trait_state"],
                            prompt_delta=_diff(char.trait_state or {}, updated["trait_state"]),
                        )
                        db.add(snap)
                await merge_alias(db, existing_id, entity["name"])
            else:
                profile = build_character_profile(entity, book.id, ch_data["number"])
                char = Character(**profile, embedding=emb)
                db.add(char)
                await db.flush()

        # Store relationships
        for rel in result["relationships"]:
            char_a = await _find_char_by_name(db, book.id, rel["character_a"])
            char_b = await _find_char_by_name(db, book.id, rel["character_b"])
            if char_a and char_b:
                r_row = CharacterRelationship(
                    book_id=book.id,
                    character_a_id=char_a.id,
                    character_b_id=char_b.id,
                    rel_type=rel.get("type", "neutral"),
                    sentiment=rel.get("sentiment"),
                    description=rel.get("description"),
                    from_chapter=ch_data["number"],
                )
                db.add(r_row)

    await db.commit()


async def _find_char_by_name(db, book_id, name: str):
    result = await db.execute(
        select(Character).where(Character.book_id == book_id, Character.name == name)
    )
    return result.scalar()


def _changed(old: dict, new: dict, delta: float = 0.15) -> bool:
    for k, v in new.items():
        if not isinstance(v, dict):
            continue
        old_conf = old.get(k, {}).get("confidence", 0) if isinstance(old.get(k), dict) else 0
        if v.get("confidence", 0) - old_conf >= delta:
            return True
    return False


def _diff(old: dict, new: dict) -> str:
    changes = []
    for k, v in new.items():
        if not isinstance(v, dict):
            continue
        old_v = old.get(k, {}).get("value") if isinstance(old.get(k), dict) else None
        new_v = v.get("value")
        if old_v and new_v and old_v != new_v:
            changes.append(f"{k}: {old_v}→{new_v}")
        elif not old_v and new_v:
            changes.append(f"+{k}: {new_v}")
    return "; ".join(changes[:5]) or "minor update"
