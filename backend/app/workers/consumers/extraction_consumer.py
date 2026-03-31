"""
Full book processing: parse → chunk → extract characters + relationships → embed.
Lazy: first N chapters immediately, rest queued.
"""
import asyncio
import uuid
from app.core.database import AsyncSessionLocal
from app.core.storage import download_book
from app.core.config import effective_tier, settings
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState
from app.models.intelligence import BookChunk, CharacterRelationship
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.extractor import extract_characters_and_relationships
from app.engine.character.deduplicator import embed_for_dedup, find_by_name_or_alias, find_similar, merge_alias
from app.engine.character.profile_builder import build_character_profile, update_profile
from app.engine.embeddings.embedder import embed_batch, embed_character
from app.parsers.chunker import chunk_text, count_tokens
from sqlalchemy import delete, update as sa_update, select
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
        all_chapters = chapters

        # Retrieve user and usage
        from app.models.user import User
        from sqlalchemy import func
        user = await db.get(User, book.user_id)
        is_free_tier = user and effective_tier(user.tier) not in ("pro", "power", "admin", "premium")

        # Initial total tokens in original file
        full_tokens = sum(count_tokens(ch["text"]) for ch in all_chapters)
        processed_tokens = full_tokens
        was_truncated = False
        ai_chapters = all_chapters

        if is_free_tier:
            # How many tokens has the user already used in other books?
            result = await db.execute(
                select(func.sum(Book.total_tokens))
                .where(Book.user_id == user.id, Book.id != book.id, Book.status != "error")
            )
            used_so_far = result.scalar() or 0
            remaining_budget = max(0, settings.FREE_TOTAL_TOKEN_BUDGET - used_so_far)

            if remaining_budget == 0:
                log.warning(f"User {book.user_id} has exhausted free token budget: {used_so_far} used.")
                await db.execute(sa_update(Book).where(Book.id == book.id).values(status="error", total_tokens=0))
                await db.commit()
                return {"error": "budget_exhausted"}

            # Partially process as many chapters as fit in remaining balance
            partial_chapters: list[dict] = []
            current_sum = 0
            for ch in all_chapters:
                ch_toks = count_tokens(ch["text"])
                if current_sum + ch_toks <= remaining_budget:
                    partial_chapters.append(ch)
                    current_sum += ch_toks
                else:
                    was_truncated = True
                    break

            if not partial_chapters:
                log.warning(f"Remaining budget ({remaining_budget}) too small for even first chapter.")
                await db.execute(sa_update(Book).where(Book.id == book.id).values(status="error", total_tokens=0))
                await db.commit()
                return {"error": "insufficient_remaining_budget"}

            ai_chapters = partial_chapters
            processed_tokens = current_sum

        # Update book with final stats
        await db.execute(
            sa_update(Book)
            .where(Book.id == book.id)
            .values(
                total_chapters=len(all_chapters),
                total_tokens=processed_tokens,
                is_truncated=was_truncated
            )
        )
        await db.commit()

        # Create lightweight chapter stubs for the full parsed book so later chapters
        # can be processed incrementally as the reader advances.
        for ch_data in all_chapters:
            await _ensure_chapter_stub(db, book, ch_data)
        await db.commit()

        # Process first N chapters immediately
        for ch_data in ai_chapters[:settings.LAZY_PROCESS_INITIAL_CHAPTERS]:
            await _process_chapter(db, book, ch_data)

        await db.execute(sa_update(Book).where(Book.id == book.id).values(status="ready"))
        await db.commit()

        log.info(f"Book {book_id} processed: {len(all_chapters)} chapters")
        return {"book_id": book_id, "chapters": len(all_chapters)}


async def _process_chapter(db, book, ch_data: dict):
    """Extract characters, relationships, store chunks for one chapter."""
    # Store chapter row + raw text in storage
    from app.core.storage import upload_text

    s3_key = f"chapters/{book.id}/{ch_data['number']}.txt"
    try:
        upload_text(s3_key, ch_data["text"])
    except Exception:
        s3_key = ""

    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == ch_data["number"])
        )
    ).scalar()
    if chapter is None:
        chapter = Chapter(
            book_id=book.id,
            number=ch_data["number"],
            title=ch_data.get("title"),
            s3_key=s3_key,
            processed=True,
        )
        db.add(chapter)
        await db.commit()
        await db.refresh(chapter)
    else:
        chapter_changed = False
        if ch_data.get("title") and (not chapter.title or not chapter.title.strip()):
            chapter.title = ch_data["title"]
            chapter_changed = True
        if s3_key and (not chapter.s3_key or not chapter.s3_key.strip()):
            chapter.s3_key = s3_key
            chapter_changed = True
        if not chapter.processed:
            chapter.processed = True
            chapter_changed = True
        if chapter_changed:
            await db.commit()
            await db.refresh(chapter)

    await db.execute(delete(BookChunk).where(BookChunk.chapter_id == chapter.id))

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

    # Batch adjacent chunks together so extraction uses fewer LLM calls per chapter.
    for chunk_batch in _group_chunks_for_extraction(chunks):
        result = await extract_characters_and_relationships("\n\n".join(chunk_batch))

        for entity in result.get("characters", []):
            if not isinstance(entity, dict):
                continue
            if not entity.get("name"):
                continue
            emb = await embed_for_dedup(entity["name"], entity.get("traits", {}))
            existing_id = await find_by_name_or_alias(db, book.id, entity["name"], entity.get("aliases", []))
            if not existing_id:
                existing_id = await find_similar(db, book.id, emb, settings.DEDUP_SIMILARITY_THRESHOLD)

            if existing_id:
                char = await db.get(Character, existing_id)
                if char:
                    updated = update_profile(char, {
                        **entity,
                        "first_chapter": ch_data["number"],
                    })
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
        for rel in result.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            if not rel.get("character_a") or not rel.get("character_b"):
                continue
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

    await consolidate_characters(db, book.id, up_to_chapter=ch_data["number"])
    await db.commit()

    if ch_data["number"] <= settings.LAZY_PROCESS_INITIAL_CHAPTERS:
        from app.workers.tasks.analysis_tasks import analyse_chapter_task

        analyse_chapter_task.apply_async(
            args=[str(chapter.id), ch_data["text"], ch_data.get("title") or ""],
            queue="analysis",
        )


async def _ensure_chapter_stub(db, book, ch_data: dict):
    from app.core.storage import upload_text

    existing = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == ch_data["number"])
        )
    ).scalar()
    s3_key = f"chapters/{book.id}/{ch_data['number']}.txt"

    if existing is None:
        try:
            upload_text(s3_key, ch_data["text"])
        except Exception:
            s3_key = ""
        db.add(
            Chapter(
                book_id=book.id,
                number=ch_data["number"],
                title=ch_data.get("title"),
                s3_key=s3_key,
                token_count=count_tokens(ch_data["text"]),
                processed=False,
            )
        )
        return

    changed = False
    if ch_data.get("title") and (not existing.title or not existing.title.strip()):
        existing.title = ch_data["title"]
        changed = True
    if ch_data.get("text") and not existing.s3_key:
        try:
            upload_text(s3_key, ch_data["text"])
            existing.s3_key = s3_key
            changed = True
        except Exception:
            pass
    if ch_data.get("text") and not existing.token_count:
        existing.token_count = count_tokens(ch_data["text"])
        changed = True
    if changed:
        await db.flush()


async def _find_char_by_name(db, book_id, name: str):
    match_id = await find_by_name_or_alias(db, book_id, name, [])
    if match_id:
        return await db.get(Character, match_id)
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


def _group_chunks_for_extraction(chunks: list[str]) -> list[list[str]]:
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for chunk in chunks:
        chunk_tokens = count_tokens(chunk)
        exceeds_token_budget = current_tokens + chunk_tokens > settings.EXTRACTION_BATCH_MAX_TOKENS
        exceeds_chunk_budget = len(current_batch) >= settings.EXTRACTION_BATCH_MAX_CHUNKS

        if current_batch and (exceeds_token_budget or exceeds_chunk_budget):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(chunk)
        current_tokens += chunk_tokens

    if current_batch:
        batches.append(current_batch)

    return batches
