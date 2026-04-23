"""
Full book processing: parse → chunk → extract characters + relationships → embed.
Lazy: first N chapters immediately, rest queued.
"""
import asyncio
import re
import uuid
from app.core.database import AsyncSessionLocal
from app.core.storage import download_book, upload_binary
from app.core.config import effective_tier, settings
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import Character, CharacterState
from app.models.intelligence import BookChunk, CharacterRelationship
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.extractor import extract_characters_and_relationships
from app.engine.character.deduplicator import (
    character_name_keys,
    embed_for_dedup,
    find_similar,
    merge_alias,
    names_equivalent,
)
from app.engine.character.profile_builder import build_character_profile, update_profile
from app.engine.embeddings.embedder import embed_batch
from app.parsers.chunker import ChunkingConfig, chunk_text, count_tokens
from app.utils.compliance.copyright_check import check_isbn
from app.utils.external.isbn_lookup import extract_isbn_from_pdf
from app.utils.book_utils import serialize_manuscript_content
from sqlalchemy import delete, func, update as sa_update, select
import logging

log = logging.getLogger("lorevia.extraction")


async def process_book(book_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        book = await db.get(Book, uuid.UUID(book_id))
        if not book:
            return {"error": "not found"}

        await db.execute(sa_update(Book).where(Book.id == book.id).values(status="processing"))
        await db.commit()

        raw = await asyncio.to_thread(download_book, book.s3_key)
        if book.format == "pdf" and not book.cover_s3_key:
            from app.parsers.pdf_parser import extract_first_page_cover

            cover = await asyncio.to_thread(extract_first_page_cover, raw)
            if cover:
                cover_bytes, content_type = cover
                book.cover_s3_key = await asyncio.to_thread(
                    upload_binary,
                    f"covers/{book.user_id}/{uuid.uuid4()}.png",
                    cover_bytes,
                    content_type,
                )
        if book.is_public and book.format == "pdf" and not book.isbn:
            detected_isbn = extract_isbn_from_pdf(raw)
            if detected_isbn:
                book.isbn = detected_isbn
        if book.is_public and book.isbn:
            copyright_info = await check_isbn(book.isbn)
            book.copyright_warning = bool(copyright_info.get("found", False))
        await db.commit()
        if book.format == "pdf":
            from app.parsers.pdf_parser import parse_pdf
            chapters = await asyncio.to_thread(parse_pdf, raw)
        else:
            from app.parsers.epub_parser import parse_epub
            chapters = await asyncio.to_thread(parse_epub, raw)
        all_chapters = chapters

        # Retrieve user and usage
        from app.models.user import User
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

        # Create lightweight chapter stubs so the library/reader know the chapter map
        # without uploading every parsed chapter body up front.
        for ch_data in all_chapters:
            await _ensure_chapter_stub(db, book, ch_data)
        await db.commit()

        # Queue chapters with their already-parsed text so workers don't need to
        # re-download and re-parse the full book for every chapter.
        from app.workers.tasks.extraction_tasks import process_chapter_task
        initial_chapters = ai_chapters[:settings.LAZY_PROCESS_INITIAL_CHAPTERS]
        remaining_chapters = ai_chapters[settings.LAZY_PROCESS_INITIAL_CHAPTERS:]

        for ch_data in initial_chapters:
            process_chapter_task.apply_async(
                args=[str(book.id), ch_data["number"], ch_data.get("title") or "", ch_data.get("text") or ""],
                queue="extraction",
            )

        for ch_data in remaining_chapters:
            process_chapter_task.apply_async(
                args=[str(book.id), ch_data["number"], ch_data.get("title") or "", ch_data.get("text") or ""],
                queue="extraction",
            )

        if was_truncated:
            await db.execute(sa_update(Book).where(Book.id == book.id).values(status="ready"))
            await db.commit()

        if settings.DEBUG:
            log.info("book_processed %s chapters=%s", book_id, len(all_chapters))
        return {"book_id": book_id, "chapters": len(all_chapters)}


async def _process_chapter(db, book, ch_data: dict):
    """Extract characters, relationships, store chunks for one chapter."""
    # Store chapter row + raw text in storage
    from app.core.storage import upload_text

    s3_key = f"chapters/{book.id}/{ch_data['number']}.txt"
    try:
        await asyncio.to_thread(
            upload_text,
            s3_key,
            serialize_manuscript_content(ch_data.get("text", ""), ch_data.get("html")),
        )
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
            word_count=_count_words(ch_data.get("text", "")),
            processed=True,
        )
        db.add(chapter)
        await db.flush()
        await _sync_chapter_media(db, book, chapter, ch_data)
    else:
        chapter_changed = False
        if ch_data.get("title") and chapter.title != ch_data["title"]:
            chapter.title = ch_data["title"]
            chapter_changed = True
        if s3_key and chapter.s3_key != s3_key:
            chapter.s3_key = s3_key
            chapter_changed = True
        if not chapter.processed:
            chapter.processed = True
            chapter_changed = True
        next_word_count = _count_words(ch_data.get("text", ""))
        if next_word_count and chapter.word_count != next_word_count:
            chapter.word_count = next_word_count
            chapter_changed = True
        if chapter_changed:
            await db.flush()
        await _sync_chapter_media(db, book, chapter, ch_data)

    await db.execute(delete(BookChunk).where(BookChunk.chapter_id == chapter.id))

    # Chunk + extract
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

    existing_characters = (
        await db.execute(
            select(Character).where(Character.book_id == book.id).order_by(Character.first_chapter, Character.created_at)
        )
    ).scalars().all()

    # Batch adjacent chunks together so extraction uses fewer LLM calls per chapter.
    extraction_batches = _group_chunks_for_extraction(chunks)
    extraction_results = await asyncio.gather(
        *(extract_characters_and_relationships("\n\n".join(chunk_batch)) for chunk_batch in extraction_batches),
        return_exceptions=True,
    )

    for result in extraction_results:
        if isinstance(result, Exception):
            continue

        character_entities = [entity for entity in result.get("characters", []) if isinstance(entity, dict) and entity.get("name")]
        dedup_embeddings = await asyncio.gather(
            *(embed_for_dedup(entity["name"], entity.get("traits", {})) for entity in character_entities),
            return_exceptions=True,
        )

        for entity, emb in zip(character_entities, dedup_embeddings):
            if not isinstance(entity, dict):
                continue
            if not entity.get("name") or isinstance(emb, Exception):
                continue
            existing_id = _find_character_id_in_cache(existing_characters, entity["name"], entity.get("aliases", []))
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
                        growth_event = entity.get("growth_event")
                        if isinstance(growth_event, dict):
                            growth_event = {
                                **growth_event,
                                "chapter": ch_data["number"],
                            }
                        snap = CharacterState(
                            character_id=existing_id,
                            at_chapter=ch_data["number"],
                            trait_snapshot=updated["trait_state"],
                            prompt_delta=_diff(char.trait_state or {}, updated["trait_state"]),
                            arc_note=entity.get("arc_summary"),
                            growth_event=growth_event if isinstance(growth_event, dict) else None,
                        )
                        db.add(snap)
                await merge_alias(db, existing_id, entity["name"])
            else:
                profile = build_character_profile(entity, book.id, ch_data["number"])
                char = Character(**profile, embedding=emb)
                db.add(char)
                await db.flush()
                existing_characters.append(char)

        # Store relationships
        for rel in result.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            if not rel.get("character_a") or not rel.get("character_b"):
                continue
            char_a = _find_character_in_cache(existing_characters, rel["character_a"])
            char_b = _find_character_in_cache(existing_characters, rel["character_b"])
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

    if await _should_consolidate_after_chapter(db, book, chapter.number):
        await consolidate_characters(db, book.id, up_to_chapter=ch_data["number"])
        await db.commit()

    if await _book_processing_complete(db, book.id):
        await db.execute(sa_update(Book).where(Book.id == book.id).values(status="ready"))
        await db.commit()

    if ch_data["number"] <= settings.LAZY_PROCESS_INITIAL_CHAPTERS:
        from app.workers.tasks.analysis_tasks import analyse_chapter_task

        analyse_chapter_task.apply_async(
            args=[str(chapter.id), ch_data["text"], ch_data.get("title") or ""],
            queue="analysis",
        )


async def _ensure_chapter_stub(db, book, ch_data: dict):
    existing = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == ch_data["number"])
        )
    ).scalar()

    if existing is None:
        chapter = Chapter(
            book_id=book.id,
            number=ch_data["number"],
            title=ch_data.get("title"),
            description=ch_data.get("description"),
            s3_key="",
            token_count=count_tokens(ch_data["text"]),
            word_count=_count_words(ch_data.get("text", "")),
            processed=False,
        )
        db.add(chapter)
        await db.flush()
        return

    changed = False
    if ch_data.get("title") and (not existing.title or not existing.title.strip()):
        existing.title = ch_data["title"]
        changed = True
    if ch_data.get("description") and (not existing.description or not existing.description.strip()):
        existing.description = ch_data["description"]
        changed = True
    if ch_data.get("text") and not existing.token_count:
        existing.token_count = count_tokens(ch_data["text"])
        changed = True
    next_word_count = _count_words(ch_data.get("text", ""))
    if next_word_count and existing.word_count != next_word_count:
        existing.word_count = next_word_count
        changed = True
    if changed:
        await db.flush()


def _find_character_id_in_cache(chars: list[Character], name: str, aliases: list[str] | None) -> uuid.UUID | None:
    candidate_keys = character_name_keys(name, aliases or [])
    if not candidate_keys:
        return None

    for char in chars:
        if candidate_keys & character_name_keys(char.name, char.aliases or []):
            return char.id
        if names_equivalent(name, aliases or [], char.name, char.aliases or []):
            return char.id
    return None


def _find_character_in_cache(chars: list[Character], name: str) -> Character | None:
    match_id = _find_character_id_in_cache(chars, name, [])
    if not match_id:
        return None
    return next((char for char in chars if char.id == match_id), None)


async def _book_processing_complete(db, book_id: uuid.UUID) -> bool:
    remaining = await db.scalar(
        select(func.count()).select_from(Chapter).where(Chapter.book_id == book_id, Chapter.processed.is_(False))
    )
    return not bool(remaining)


async def _should_consolidate_after_chapter(db, book: Book, chapter_number: int) -> bool:
    if chapter_number <= settings.LAZY_PROCESS_INITIAL_CHAPTERS:
        return True
    return await _book_processing_complete(db, book.id)


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


def _count_words(text: str) -> int:
    cleaned = re.sub(r"\[\[IMAGE:[^\]]+\]\]", " ", text or "")
    return len(re.findall(r"\b[\w']+\b", cleaned))


async def _sync_chapter_media(db, book: Book, chapter: Chapter, ch_data: dict) -> None:
    images = ch_data.get("images") or []
    await db.execute(delete(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id))
    if not images:
        return

    for index, image in enumerate(images):
        raw = image.get("bytes")
        marker = image.get("marker")
        if not raw or not marker:
            continue
        filename = image.get("filename") or f"{uuid.uuid4().hex}.bin"
        storage_key = f"chapter-media/{book.id}/{chapter.number}/{index}-{filename}"
        await asyncio.to_thread(upload_binary, storage_key, raw, image.get("content_type"))
        db.add(
            ChapterMedia(
                book_id=book.id,
                chapter_id=chapter.id,
                marker=marker,
                asset_type="image",
                content_type=image.get("content_type"),
                storage_key=storage_key,
                caption=None,
                sort_order=index,
            )
        )
