from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
import re

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book, upload_binary
from app.engine.world.dependency_graph import build_dependency_graph
from app.engine.world.extractor import extract_world_elements_from_text, infer_element_type
from app.engine.world.gap_detector import detect_consistency_flags
from app.models.book import Book, Chapter, SeriesBook
from app.models.character import Character
from app.models.intelligence import ChapterSummary, WikiEntry, WorldBuildingDocument, WorldElement, WorldGapAnalysis, WorldNote
from app.utils.book_utils import (
    clean_manuscript_html,
    deserialize_manuscript_content,
    parse_import_upload,
    serialize_manuscript_content,
)

GAP_GROUP_META: dict[str, tuple[str, str]] = {
    "story_conflicts": (
        "Story conflicts",
        "The manuscript and the world corpus disagree about the same lore element.",
    ),
    "missing_in_story": (
        "Missing in story",
        "The world corpus documents lore that barely appears in the story manuscript.",
    ),
    "missing_in_world": (
        "Missing in world corpus",
        "Story-facing lore appears in chapters but is not captured in the world-building workspace.",
    ),
    "character_gaps": (
        "Character reference gaps",
        "Core character facts are active in the story but absent from the world corpus.",
    ),
    "timeline_gaps": (
        "Timeline watchlist",
        "Lore only appears late or too lightly in the manuscript to feel grounded.",
    ),
}
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "of",
    "to",
    "in",
    "for",
    "with",
    "on",
    "at",
    "from",
    "by",
    "is",
    "are",
    "was",
    "were",
}
CLIMATE_BUCKETS = {
    "cold": {"cold", "frozen", "snow", "snowbound", "icy", "ice", "winter"},
    "hot": {"desert", "arid", "drought", "sun-scorched", "burning", "heat"},
    "wet": {"rain", "storm", "flooded", "marsh", "mist", "wet"},
}


def classify_world_intent(query: str | None) -> str:
    text = (query or "").strip().lower()
    if any(token in text for token in ("use", "integrate", "where", "thread", "story", "scene")):
        return "story_integration"
    if any(token in text for token in ("missing", "gap", "incomplete", "contradiction", "consistency", "worldbuild")):
        return "gap_detection"
    return "gap_detection"


async def list_world_building_documents(
    db: AsyncSession,
    book: Book,
    *,
    include_inactive: bool = False,
) -> list[WorldBuildingDocument]:
    stmt = select(WorldBuildingDocument).where(WorldBuildingDocument.book_id == book.id)
    if not include_inactive:
        stmt = stmt.where(WorldBuildingDocument.is_active.is_(True))
    stmt = stmt.order_by(WorldBuildingDocument.updated_at.desc(), WorldBuildingDocument.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def get_world_building_document(
    db: AsyncSession,
    book: Book,
    document_id: uuid.UUID,
    *,
    include_inactive: bool = True,
) -> WorldBuildingDocument:
    document = await db.get(WorldBuildingDocument, document_id)
    if not document or document.book_id != book.id or (not include_inactive and not document.is_active):
        raise HTTPException(404, "World-building document not found")
    return document


async def load_world_building_document_payload(document: WorldBuildingDocument) -> dict[str, str | None]:
    try:
        raw = download_book(document.s3_key)
    except Exception as exc:
        raise HTTPException(404, "World-building document content is unavailable") from exc
    return deserialize_manuscript_content(raw)


async def prepare_world_building_uploads(
    *,
    files: list[tuple[str, bytes]],
    text: str | None,
    html: str | None,
    title: str | None,
) -> list[dict]:
    uploads: list[dict] = []
    cleaned_title = " ".join((title or "").split()).strip() or None
    cleaned_html = clean_manuscript_html(html) if html else None

    if text and text.strip():
        body = text.strip()
        uploads.append(
            {
                "title": cleaned_title or "Worldbuilding Manuscript",
                "source_name": cleaned_title or "worldbuilding",
                "text": body,
                "html": cleaned_html,
            }
        )

    for filename, raw in files:
        parsed = await parse_import_upload(filename, raw, split_into_chapters=False)
        if not parsed:
            continue
        merged_text = "\n\n".join(str(item.get("text") or "").strip() for item in parsed if str(item.get("text") or "").strip()).strip()
        merged_html = "\n".join(str(item.get("html") or "").strip() for item in parsed if str(item.get("html") or "").strip()).strip() or None
        if not merged_text:
            continue
        uploads.append(
            {
                "title": cleaned_title or _filename_title(filename),
                "source_name": filename,
                "text": merged_text,
                "html": clean_manuscript_html(merged_html) if merged_html else None,
            }
        )

    return uploads


async def create_world_building_documents(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    documents: list[dict],
    replace_existing: bool = False,
) -> list[WorldBuildingDocument]:
    if not documents:
        raise HTTPException(400, "No world-building content was provided")

    if replace_existing:
        active_documents = await list_world_building_documents(db, book)
        for current in active_documents:
            current.is_active = False
            current.archived_at = datetime.now(UTC)

    created: list[WorldBuildingDocument] = []
    for payload in documents:
        text = str(payload.get("text") or "").strip()
        if not text:
            continue
        title = " ".join(str(payload.get("title") or "").split()).strip() or "Worldbuilding Manuscript"
        html = str(payload.get("html") or "").strip() or None
        storage_key = upload_binary(
            f"worldbuilding/{user_id}/{book.id}/{uuid.uuid4()}.json",
            serialize_manuscript_content(text, html).encode("utf-8"),
            "application/json",
        )
        document = WorldBuildingDocument(
            book_id=book.id,
            title=title,
            source_name=" ".join(str(payload.get("source_name") or "").split()).strip() or None,
            s3_key=storage_key,
            word_count=_count_words(text),
            is_active=True,
        )
        db.add(document)
        created.append(document)

    if not created:
        raise HTTPException(400, "No importable world-building content was found")

    await db.flush()
    await sync_world_document_elements(db, book)
    return created


async def update_world_building_document(
    db: AsyncSession,
    *,
    book: Book,
    document: WorldBuildingDocument,
    title: str | None,
    text: str,
    html: str | None = None,
) -> WorldBuildingDocument:
    body = text.strip()
    if not body:
        raise HTTPException(400, "World-building document text is required")

    next_title = " ".join((title or document.title or "").split()).strip() or "Worldbuilding Manuscript"
    cleaned_html = clean_manuscript_html(html) if html else None
    document.title = next_title
    document.word_count = _count_words(body)
    document.s3_key = upload_binary(
        f"worldbuilding/{book.user_id}/{book.id}/{uuid.uuid4()}.json",
        serialize_manuscript_content(body, cleaned_html).encode("utf-8"),
        "application/json",
    )
    document.updated_at = datetime.now(UTC)
    document.is_active = True
    document.archived_at = None
    await db.flush()
    await sync_world_document_elements(db, book)
    return document


async def delete_world_building_document(
    db: AsyncSession,
    *,
    book: Book,
    document: WorldBuildingDocument,
) -> None:
    if document.book_id != book.id:
        raise HTTPException(404, "World-building document not found")
    await db.delete(document)
    await db.flush()
    await sync_world_document_elements(db, book)


async def extract_world_elements(db: AsyncSession, book: Book) -> list[WorldElement]:
    await sync_world_document_elements(db, book)
    rows = list(
        (
            await db.execute(
                select(WorldElement)
                .where(WorldElement.book_id == book.id)
                .order_by(WorldElement.source_scope.asc(), WorldElement.name.asc())
            )
        ).scalars().all()
    )
    return rows


async def generate_wiki_from_manuscript(db: AsyncSession, book: Book) -> list[WikiEntry]:
    elements = await _collect_story_elements(db, book)
    summaries = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id, ChapterSummary.mode == "detailed")
            .order_by(Chapter.number.asc())
        )
    ).all()
    characters = (
        await db.execute(select(Character.id, Character.name).where(Character.book_id == book.id))
    ).all()
    character_ids = [str(character_id) for character_id, _ in characters[:5]]

    existing = (
        await db.execute(select(WikiEntry).where(WikiEntry.book_id == book.id))
    ).scalars().all()
    by_name = {entry.name.strip().lower(): entry for entry in existing if entry.name}
    touched: list[WikiEntry] = []

    for element in elements:
        key = element.name.strip().lower()
        if not key:
            continue
        metadata = element.analysis_metadata or {}
        entry = by_name.get(key)
        description = (element.description or "").strip() or f"{element.name} appears in the manuscript and has not been summarized yet."
        if entry is None:
            entry = WikiEntry(
                book_id=book.id,
                entry_type=_map_element_to_wiki_type(element.element_type),
                name=element.name.strip(),
                description=description,
                first_mention=int(metadata.get("chapter_number") or 0) or None,
                related_char_ids=character_ids or None,
            )
            db.add(entry)
            by_name[key] = entry
        else:
            entry.entry_type = _map_element_to_wiki_type(element.element_type)
            entry.description = description if len(description) >= len(entry.description or "") else entry.description
            entry.first_mention = entry.first_mention or (int(metadata.get("chapter_number") or 0) or None)
            entry.related_char_ids = entry.related_char_ids or (character_ids or None)
        touched.append(entry)

    for chapter_number, chapter_title, key_events in summaries:
        if not isinstance(key_events, list):
            continue
        for event in key_events[:3]:
            if not isinstance(event, dict):
                continue
            name = " ".join(str(event.get("event_title") or event.get("event") or "").split()).strip()
            if not name:
                continue
            key = name.lower()
            entry = by_name.get(key)
            description = " ".join(str(event.get("description") or event.get("impact") or "").split()).strip() or (
                f"{name} is tracked as a chapter event in {chapter_title or f'chapter {chapter_number}'}."
            )
            if entry is None:
                entry = WikiEntry(
                    book_id=book.id,
                    entry_type="event",
                    name=name,
                    description=description,
                    first_mention=chapter_number,
                    related_char_ids=character_ids or None,
                )
                db.add(entry)
                by_name[key] = entry
            else:
                entry.entry_type = entry.entry_type or "event"
                entry.description = description if len(description) >= len(entry.description or "") else entry.description
                entry.first_mention = entry.first_mention or chapter_number
            touched.append(entry)

    await db.flush()
    return sorted(touched, key=lambda item: (item.entry_type, item.name.lower()))


async def build_world_logic_response(db: AsyncSession, book: Book, query: str, mode: str) -> dict:
    elements = await extract_world_elements(db, book)
    context = build_world_context(elements)
    analysis = await detect_integration_analysis(db, book) if mode == "story_integration" else await detect_world_gaps(db, book)
    logic_alerts = list((analysis.get("consistency_flags") or [])[:4])
    suggestions = list(
        (analysis.get("integration_opportunities") or analysis.get("priority_gaps") or [])[:5]
    )

    ranked_elements = _rank_world_elements_for_query(elements, query)
    citations = [
        {
            "id": str(element.id),
            "name": element.name,
            "element_type": element.element_type,
            "source_scope": element.source_scope,
        }
        for element in ranked_elements[:5]
    ]
    simulation_steps = [
        f"Canon focus: {element.name} behaves as a {element.element_type} with {element.source_scope} support."
        for element in ranked_elements[:3]
    ]
    if not simulation_steps:
        simulation_steps.append("No direct lore entity matched the query, so the simulator is leaning on broader world context.")

    if any(token in query.lower() for token in ("react", "response", "respond", "kingdom", "court", "faction")):
        answer = (
            f"World logic mode traced likely reactions from the strongest matching lore nodes. "
            f"Start with {ranked_elements[0].name if ranked_elements else 'the current canon'}, then pressure-test whether each response matches the manuscript and world corpus.\n"
            f"{context[:900]}"
        )
    elif mode == "story_integration":
        answer = (
            f"Integration simulation found {len(suggestions)} ways to move documented lore onto the page more clearly. "
            f"Use the matched elements below to choose the cleanest insertion point.\n{context[:900]}"
        )
    else:
        answer = (
            f"World logic scan found {len(suggestions)} continuity or coverage issues that matter most for this question. "
            f"Use the alerts to decide whether the manuscript or the lore corpus should be treated as canonical.\n{context[:900]}"
        )
    return {
        "mode": mode,
        "answer": answer,
        "citations": citations,
        "suggestions": suggestions,
        "logic_alerts": logic_alerts,
        "simulation_steps": simulation_steps,
    }


async def sync_world_document_elements(db: AsyncSession, book: Book) -> list[WorldElement]:
    documents = await list_world_building_documents(db, book)
    await db.execute(
        delete(WorldElement).where(
            WorldElement.book_id == book.id,
            WorldElement.source_scope == "worldbuilding",
        )
    )
    await db.flush()

    created: list[WorldElement] = []
    for document in documents:
        payload = await load_world_building_document_payload(document)
        text = str(payload.get("text") or "")
        for candidate in extract_world_elements_from_text(text):
            name = str(candidate.get("name") or "").strip()
            if not name:
                continue
            element = WorldElement(
                book_id=book.id,
                series_id=book.primary_series_id,
                source_book_id=book.id,
                world_document_id=document.id,
                source_scope="worldbuilding",
                element_type=str(candidate.get("element_type") or infer_element_type(name, str(candidate.get("description") or ""))),
                name=name,
                description=str(candidate.get("description") or "").strip() or None,
                usage_count=int(candidate.get("usage_count") or 1),
                analysis_metadata={
                    "source": "world_document",
                    "world_document_title": document.title,
                    "world_document_source_name": document.source_name,
                },
                is_series_canonical=bool(book.primary_series_id),
            )
            db.add(element)
            created.append(element)
    await db.flush()
    return created


async def ingest_world_elements_from_chapter(
    db: AsyncSession,
    *,
    book: Book,
    chapter: Chapter,
    chapter_text: str,
) -> list[WorldElement]:
    extracted = extract_world_elements_from_text(chapter_text, chapter_number=chapter.number)
    if not extracted:
        return []

    existing = (
        await db.execute(
            select(WorldElement).where(
                WorldElement.book_id == book.id,
                WorldElement.source_scope == "story",
            )
        )
    ).scalars().all()
    by_name = {element.name.strip().lower(): element for element in existing if element.name}
    touched: list[WorldElement] = []

    for candidate in extracted:
        key = str(candidate.get("name") or "").strip().lower()
        if not key:
            continue
        current = by_name.get(key)
        description = str(candidate.get("description") or "").strip() or None
        usage_increment = int(candidate.get("usage_count") or 1)
        if current is None:
            current = WorldElement(
                book_id=book.id,
                series_id=book.primary_series_id,
                source_book_id=book.id,
                source_scope="story",
                element_type=str(candidate.get("element_type") or "culture"),
                name=str(candidate.get("name") or "").strip(),
                description=description,
                usage_count=usage_increment,
                analysis_metadata={
                    "source": "chapter_text",
                    "chapter_number": chapter.number,
                    "chapter_title": chapter.title,
                },
                is_series_canonical=bool(book.primary_series_id),
            )
            db.add(current)
            by_name[key] = current
        else:
            current.usage_count = int(current.usage_count or 0) + usage_increment
            if description and (not current.description or len(description) > len(current.description)):
                current.description = description
            metadata = dict(current.analysis_metadata or {})
            metadata.setdefault("chapter_number", chapter.number)
            metadata.setdefault("chapter_title", chapter.title)
            current.analysis_metadata = metadata
        touched.append(current)

    await db.flush()
    return touched


def build_world_context(elements: list[WorldElement]) -> str:
    lines: list[str] = []
    for element in elements[:40]:
        scope = "world" if element.source_scope == "worldbuilding" else "story"
        lines.append(
            f"- {element.name} [{element.element_type} · {scope}] usage={element.usage_count}: "
            f"{(element.description or 'No description.')[:180]}"
        )
    return "\n".join(lines)


async def build_series_world_context(db: AsyncSession, series_id: uuid.UUID) -> str:
    book_ids = list(
        (
            await db.execute(select(SeriesBook.book_id).where(SeriesBook.series_id == series_id))
        ).scalars().all()
    )
    if not book_ids:
        return ""
    elements = list(
        (
            await db.execute(select(WorldElement).where(WorldElement.book_id.in_(book_ids)))
        ).scalars().all()
    )
    return build_world_context(elements)


async def detect_world_gaps(db: AsyncSession, book: Book) -> dict:
    documents = await list_world_building_documents(db, book)
    document_elements = await sync_world_document_elements(db, book)
    story_elements = await _collect_story_elements(db, book)
    characters = await _collect_story_characters(db, book)
    story_by_name = _collapse_elements([_serialize_world_element(item) for item in story_elements])
    world_by_name = _collapse_elements([_serialize_world_element(item) for item in document_elements])
    world_corpus_text = "\n".join(item.get("description") or "" for item in world_by_name.values()).lower()

    grouped_items: dict[str, list[dict]] = defaultdict(list)

    for key, world_item in world_by_name.items():
        story_match = story_by_name.get(key)
        if story_match is None:
            grouped_items["missing_in_story"].append(
                _build_gap_item(
                    category="missing_in_story",
                    severity="high",
                    title=f"{world_item['name']} is missing from the story manuscript",
                    description="This lore item is documented in the world-building corpus but does not appear in the current story manuscript.",
                    suggested_fix=f"Seed {world_item['name']} into a chapter scene, summary beat, or character conversation so the manuscript reflects the reference lore.",
                    world_item=world_item,
                    priority=8,
                )
            )
            continue

        if _descriptions_conflict(str(world_item.get("description") or ""), str(story_match.get("description") or "")):
            grouped_items["story_conflicts"].append(
                _build_gap_item(
                    category="story_conflicts",
                    severity="critical",
                    title=f"{world_item['name']} conflicts with the story manuscript",
                    description="The story manuscript describes this lore differently from the world-building corpus.",
                    suggested_fix=f"Choose the canonical version of {world_item['name']} and update either the world document or the relevant story chapter to match it.",
                    world_item=world_item,
                    story_item=story_match,
                    priority=10,
                )
            )
            continue

        if int(story_match.get("usage_count") or 0) <= 1:
            grouped_items["timeline_gaps"].append(
                _build_gap_item(
                    category="timeline_gaps",
                    severity="medium",
                    title=f"{world_item['name']} only lands lightly in the manuscript",
                    description="The lore exists in the world corpus, but it only surfaces once or very late in the story material.",
                    suggested_fix=f"Foreshadow {world_item['name']} earlier or reinforce it across multiple chapters so readers can track it before payoff moments.",
                    world_item=world_item,
                    story_item=story_match,
                    priority=6,
                )
            )

    for key, story_item in story_by_name.items():
        if key in world_by_name or int(story_item.get("usage_count") or 0) < 2:
            continue
        grouped_items["missing_in_world"].append(
            _build_gap_item(
                category="missing_in_world",
                severity="medium",
                title=f"{story_item['name']} appears in the story but not in the world corpus",
                description="Readers can encounter this lore in the manuscript, but it is not captured in the reference documents yet.",
                suggested_fix=f"Add a worldbuilding entry for {story_item['name']} so the reference corpus stays aligned with the manuscript.",
                story_item=story_item,
                priority=5,
            )
        )

    for character in characters:
        if not character["should_watch"]:
            continue
        if character["name"].lower() in world_corpus_text:
            continue
        grouped_items["character_gaps"].append(
            {
                "id": f"character-gap-{character['id']}",
                "category": "character_gaps",
                "severity": "medium",
                "title": f"{character['name']} is active in the story but absent from world notes",
                "description": "This character has meaningful story presence, but the world-building corpus does not mention them.",
                "suggested_fix": f"Add a worldbuilding note for {character['name']} covering role, affiliations, and any lore rules that affect them.",
                "world_evidence": None,
                "story_evidence": character["story_evidence"],
                "world_document_id": None,
                "world_document_title": None,
                "story_chapter_number": character["chapter_number"],
                "story_chapter_title": None,
                "character_name": character["name"],
                "priority": 5,
            }
        )

    gap_groups = []
    for key, items in grouped_items.items():
        label, description = GAP_GROUP_META.get(key, (key.replace("_", " ").title(), None))
        ordered_items = sorted(items, key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or "")))
        gap_groups.append(
            {
                "key": key,
                "label": label,
                "description": description,
                "items": ordered_items,
            }
        )
    gap_groups.sort(key=lambda item: max((int(entry.get("priority") or 0) for entry in item["items"]), default=0), reverse=True)

    gap_categories = {group["key"]: group["items"] for group in gap_groups}
    priority_gaps = [item for group in gap_groups for item in group["items"]]
    priority_gaps.sort(key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or "")))
    priority_gaps = priority_gaps[:12]
    consistency_flags = detect_consistency_flags([_serialize_world_element(item) for item in document_elements])

    analysis = await _upsert_world_analysis(
        db,
        book_id=book.id,
        series_id=book.primary_series_id,
        mode="gap_detection",
        gap_categories=gap_categories,
        priority_gaps=priority_gaps,
        integration_opportunities=[],
        consistency_flags=consistency_flags,
    )
    _apply_gap_scores(document_elements, priority_gaps)

    return {
        "mode": "gap_detection",
        "generated_at": analysis.generated_at,
        "gap_categories": gap_categories,
        "gap_groups": gap_groups,
        "priority_gaps": priority_gaps,
        "consistency_flags": consistency_flags,
        "world_elements": [_serialize_world_element(element) for element in document_elements],
        "world_documents": [_serialize_world_document(document) for document in documents],
    }


async def detect_integration_analysis(db: AsyncSession, book: Book) -> dict:
    documents = await list_world_building_documents(db, book)
    document_elements = await sync_world_document_elements(db, book)
    story_elements = await _collect_story_elements(db, book)
    story_by_name = _collapse_elements([_serialize_world_element(item) for item in story_elements])
    integration_opportunities: list[dict] = []

    for element in document_elements:
        story_match = story_by_name.get(element.name.lower())
        story_match_data = story_match or {}
        usage_count = int(story_match_data.get("usage_count") or 0)
        if usage_count >= 2:
            continue
        metadata = element.analysis_metadata or {}
        target_chapter = story_match_data.get("chapter_number")
        integration_opportunities.append(
            {
                "id": f"integration-{str(element.id)}",
                "element_name": element.name,
                "element_type": element.element_type,
                "description": f"{element.name} is present in the world corpus but underused in the manuscript.",
                "suggestions": [
                    f"Introduce {element.name} in a character-facing scene before it becomes plot-critical.",
                    f"Reference {element.name} in chapter summaries, dialogue, or setting description so it feels lived-in.",
                ],
                "target_chapter": target_chapter,
                "target_chapter_title": story_match_data.get("chapter_title"),
                "priority": 8 if usage_count == 0 else 6,
                "world_document_id": str(element.world_document_id) if element.world_document_id else None,
                "world_document_title": metadata.get("world_document_title"),
            }
        )

    integration_opportunities.sort(key=lambda item: (-int(item.get("priority") or 0), item["element_name"].lower()))
    consistency_flags = detect_consistency_flags([_serialize_world_element(item) for item in document_elements])
    analysis = await _upsert_world_analysis(
        db,
        book_id=book.id,
        series_id=book.primary_series_id,
        mode="story_integration",
        gap_categories={},
        priority_gaps=[],
        integration_opportunities=integration_opportunities,
        consistency_flags=consistency_flags,
    )
    _apply_integration_scores(document_elements, integration_opportunities)
    return {
        "mode": "story_integration",
        "generated_at": analysis.generated_at,
        "integration_opportunities": integration_opportunities,
        "consistency_flags": consistency_flags,
        "world_elements": [_serialize_world_element(element) for element in document_elements],
        "world_documents": [_serialize_world_document(document) for document in documents],
        "dependency_graph": build_dependency_graph([_serialize_world_element(element) for element in document_elements]),
    }


async def save_world_note(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    world_element_id: uuid.UUID | None,
    world_document_id: uuid.UUID | None,
    note_type: str,
    chapter_number: int | None,
    title: str | None,
    body: str,
    priority: str,
    status: str,
    linked_gap_id: str | None = None,
    linked_integration_id: str | None = None,
    context_label: str | None = None,
    suggested_fix: str | None = None,
) -> WorldNote:
    note = WorldNote(
        user_id=user_id,
        book_id=book_id,
        world_element_id=world_element_id,
        world_document_id=world_document_id,
        note_type=note_type,
        chapter_number=chapter_number,
        title=title,
        body=body,
        priority=priority,
        status=status,
        linked_gap_id=linked_gap_id,
        linked_integration_id=linked_integration_id,
        context_label=context_label,
        suggested_fix=suggested_fix,
        addressed_at=datetime.now(UTC) if status == "addressed" else None,
    )
    db.add(note)
    await db.flush()
    return note


def _serialize_world_document(document: WorldBuildingDocument) -> dict:
    return {
        "id": str(document.id),
        "book_id": str(document.book_id),
        "title": document.title,
        "source_name": document.source_name,
        "word_count": document.word_count,
        "is_active": bool(document.is_active),
        "archived_at": document.archived_at,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _serialize_world_element(element: WorldElement) -> dict:
    metadata = element.analysis_metadata or {}
    return {
        "id": str(element.id),
        "book_id": str(element.book_id),
        "series_id": str(element.series_id) if element.series_id else None,
        "world_document_id": str(element.world_document_id) if element.world_document_id else None,
        "source_scope": element.source_scope or "story",
        "element_type": element.element_type,
        "name": element.name,
        "description": element.description,
        "parent_element_id": str(element.parent_element_id) if element.parent_element_id else None,
        "dependencies": list(element.dependencies or []),
        "usage_count": int(element.usage_count or 0),
        "gap_score": element.gap_score,
        "integration_score": element.integration_score,
        "suggestions": list(element.suggestions or []),
        "edited_by_author": bool(element.edited_by_author),
        "is_series_canonical": bool(element.is_series_canonical),
        "created_at": element.created_at,
        "updated_at": element.updated_at,
        "chapter_number": metadata.get("chapter_number"),
        "chapter_title": metadata.get("chapter_title"),
        "world_document_title": metadata.get("world_document_title"),
    }


async def _collect_story_elements(db: AsyncSession, book: Book) -> list[WorldElement]:
    rows = list(
        (
            await db.execute(
                select(WorldElement).where(
                    WorldElement.book_id == book.id,
                    WorldElement.source_scope == "story",
                )
            )
        ).scalars().all()
    )
    if rows:
        return rows

    chapter_rows = (
        await db.execute(
            select(Chapter.id, Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    collapsed: dict[str, dict] = {}
    for _, chapter_number, chapter_title, s3_key in chapter_rows:
        if not s3_key:
            continue
        try:
            stored = deserialize_manuscript_content(download_book(s3_key))
        except Exception:
            continue
        text = str(stored.get("text") or "")
        for candidate in extract_world_elements_from_text(text):
            name = str(candidate.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            current = collapsed.get(key)
            description = str(candidate.get("description") or "").strip() or None
            usage_count = int(candidate.get("usage_count") or 1)
            if current is None:
                current = {
                    "element_type": str(candidate.get("element_type") or infer_element_type(name, description or "")),
                    "name": name,
                    "description": description,
                    "usage_count": usage_count,
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                }
                collapsed[key] = current
            else:
                current["usage_count"] = int(current.get("usage_count") or 0) + usage_count
                if description and (not current.get("description") or len(description) > len(str(current.get("description") or ""))):
                    current["description"] = description

    story_elements: list[WorldElement] = []
    for item in collapsed.values():
        story_elements.append(
            WorldElement(
                id=uuid.uuid4(),
                book_id=book.id,
                series_id=book.primary_series_id,
                source_book_id=book.id,
                source_scope="story",
                element_type=str(item["element_type"]),
                name=str(item["name"]),
                description=str(item.get("description") or "") or None,
                usage_count=int(item.get("usage_count") or 0),
                analysis_metadata={
                    "source": "chapter_text_snapshot",
                    "chapter_number": item.get("chapter_number"),
                    "chapter_title": item.get("chapter_title"),
                },
                is_series_canonical=bool(book.primary_series_id),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    return story_elements


async def _collect_story_characters(db: AsyncSession, book: Book) -> list[dict]:
    rows = (
        await db.execute(
            select(
                Character.id,
                Character.name,
                Character.role,
                Character.first_chapter,
                Character.arc_summary,
                Character.mention_count,
            )
            .where(Character.book_id == book.id)
            .order_by(Character.mention_count.desc(), Character.first_chapter, Character.name)
        )
    ).all()
    results = []
    for character_id, name, role, first_chapter, arc_summary, mention_count in rows:
        story_evidence = f"{name} appears in the manuscript"
        if role:
            story_evidence += f" as {role}"
        if arc_summary:
            story_evidence += f". Arc note: {arc_summary[:160]}"
        results.append(
            {
                "id": str(character_id),
                "name": name,
                "chapter_number": first_chapter,
                "story_evidence": story_evidence,
                "should_watch": int(mention_count or 0) >= 4 or role in {"mc", "sc"},
            }
        )
    return results


def _map_element_to_wiki_type(element_type: str) -> str:
    normalized = " ".join((element_type or "").split()).strip().lower()
    if normalized in {"geography", "location", "city", "kingdom", "region"}:
        return "location"
    if normalized in {"faction", "religion", "culture", "government"}:
        return "faction"
    if normalized in {"artifact", "item", "technology", "weapon"}:
        return "item"
    if normalized in {"event", "history"}:
        return "event"
    return "concept"


def _rank_world_elements_for_query(elements: list[WorldElement], query: str) -> list[WorldElement]:
    tokens = {token for token in re.findall(r"[a-z0-9']+", (query or "").lower()) if token not in STOPWORDS}

    def score(element: WorldElement) -> tuple[int, int, str]:
        haystack = f"{element.name} {element.description or ''} {element.element_type}".lower()
        overlap = sum(1 for token in tokens if token in haystack)
        return (overlap, int(element.usage_count or 0), element.name.lower())

    return sorted(elements, key=score, reverse=True)


def _collapse_elements(items: list[dict]) -> dict[str, dict]:
    collapsed: dict[str, dict] = {}
    for item in items:
        key = str(item.get("name") or "").strip().lower()
        if not key:
            continue
        current = collapsed.get(key)
        if current is None:
            collapsed[key] = dict(item)
            continue
        current["usage_count"] = int(current.get("usage_count") or 0) + int(item.get("usage_count") or 0)
        current.setdefault("chapter_number", item.get("chapter_number"))
        current.setdefault("chapter_title", item.get("chapter_title"))
        current.setdefault("world_document_id", item.get("world_document_id"))
        current.setdefault("world_document_title", item.get("world_document_title"))
        description = str(item.get("description") or "").strip()
        current_description = str(current.get("description") or "").strip()
        if description and len(description) > len(current_description):
            current["description"] = description
    return collapsed


def _build_gap_item(
    *,
    category: str,
    severity: str,
    title: str,
    description: str,
    suggested_fix: str,
    priority: int,
    world_item: dict | None = None,
    story_item: dict | None = None,
) -> dict:
    if world_item is not None:
        item_name = str(world_item.get("name") or "")
        world_evidence = str(world_item.get("description") or "").strip() or None
        world_document_id = str(world_item.get("world_document_id") or "") or None
        world_document_title = str(world_item.get("world_document_title") or "").strip() or None
    else:
        item_name = str(story_item.get("name") or "") if story_item else ""
        world_evidence = None
        world_document_id = None
        world_document_title = None
    if story_item is not None:
        story_evidence = str(story_item.get("description") or "").strip() or None
        story_chapter_number = int(story_item.get("chapter_number") or 0) or None
        story_chapter_title = str(story_item.get("chapter_title") or "").strip() or None
    else:
        story_evidence = None
        story_chapter_number = None
        story_chapter_title = None
    return {
        "id": f"{category}-{item_name.lower().replace(' ', '-')}",
        "category": category,
        "severity": severity,
        "title": title,
        "description": description,
        "suggested_fix": suggested_fix,
        "world_evidence": world_evidence,
        "story_evidence": story_evidence,
        "world_document_id": world_document_id,
        "world_document_title": world_document_title,
        "story_chapter_number": story_chapter_number,
        "story_chapter_title": story_chapter_title,
        "character_name": None,
        "priority": priority,
    }


def _descriptions_conflict(left: str, right: str) -> bool:
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right or normalized_left == normalized_right:
        return False

    left_numbers = {token for token in normalized_left.split() if token.isdigit()}
    right_numbers = {token for token in normalized_right.split() if token.isdigit()}
    if left_numbers and right_numbers and left_numbers != right_numbers:
        return True

    left_bucket = _climate_bucket(normalized_left)
    right_bucket = _climate_bucket(normalized_right)
    if left_bucket and right_bucket and left_bucket != right_bucket:
        return True

    left_tokens = {token for token in normalized_left.split() if token not in STOPWORDS}
    right_tokens = {token for token in normalized_right.split() if token not in STOPWORDS}
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return union > 0 and (overlap / union) < 0.2


def _climate_bucket(text: str) -> str | None:
    tokens = set(text.split())
    for name, words in CLIMATE_BUCKETS.items():
        if tokens & words:
            return name
    return None


def _normalize_text(value: str) -> str:
    return " ".join((value or "").replace("\n", " ").replace("\r", " ").split()).strip().lower()


def _count_words(text: str) -> int:
    cleaned = " ".join((text or "").split()).strip()
    return len(cleaned.split()) if cleaned else 0


def _filename_title(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in cleaned.split()) or "Worldbuilding Manuscript"


async def _upsert_world_analysis(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    series_id: uuid.UUID | None,
    mode: str,
    gap_categories: dict,
    priority_gaps: list[dict],
    integration_opportunities: list[dict],
    consistency_flags: list[dict],
) -> WorldGapAnalysis:
    existing = (
        await db.execute(
            select(WorldGapAnalysis)
            .where(WorldGapAnalysis.book_id == book_id, WorldGapAnalysis.analysis_mode == mode)
            .order_by(WorldGapAnalysis.generated_at.desc())
        )
    ).scalars().first()
    if existing is None:
        existing = WorldGapAnalysis(book_id=book_id, series_id=series_id, analysis_mode=mode)
        db.add(existing)
    existing.gap_categories = gap_categories
    existing.priority_gaps = priority_gaps
    existing.integration_opportunities = integration_opportunities
    existing.consistency_flags = consistency_flags
    existing.generated_at = datetime.now(UTC)
    await db.flush()
    return existing


def _apply_gap_scores(elements: list[WorldElement], priority_gaps: list[dict]) -> None:
    high_priority_names = {
        str(item.get("title") or "").split(" is ")[0].lower()
        for item in priority_gaps
        if str(item.get("title") or "").strip()
    }
    now = datetime.now(UTC)
    for element in elements:
        if element.name.lower() in high_priority_names:
            element.gap_score = 0.95
        else:
            element.gap_score = min(0.9, max(0.15, 1.0 / max(int(element.usage_count or 1), 1)))
        element.last_gap_analysis = now


def _apply_integration_scores(elements: list[WorldElement], integration_opportunities: list[dict]) -> None:
    by_name = {str(item.get("element_name") or "").lower(): item for item in integration_opportunities}
    now = datetime.now(UTC)
    for element in elements:
        suggestion_payload = by_name.get(element.name.lower())
        element.integration_score = 0.2 if suggestion_payload else 0.9
        if suggestion_payload:
            element.suggestions = list(suggestion_payload.get("suggestions") or [])
        element.last_integration_analysis = now
