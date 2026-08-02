from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.world.extractor import (
    extract_world_elements_from_text,
    infer_element_type,
)
from app.models.book import Book, Chapter, SeriesBook
from app.models.intelligence import (
    WorldBuildingDocument,
    WorldElement,
)
from app.utils.world_building_analysis_payload_utils import (
    build_integration_analysis_payload,
    build_world_gap_analysis_payload,
    empty_gap_analysis_payload,
    empty_integration_analysis_payload,
)
from app.utils.world_building_candidate_record_utils import (
    collect_story_candidate_records,
    collect_world_document_candidate_records,
)
from app.utils.world_building_candidate_utils import (
    _apply_character_and_override_resolution,
    _dedupe_strings,
    _merge_claims,
)
from app.utils.world_building_conflict_utils import (
    _build_cross_source_conflict_detail,
    _claim_phrase,
    _claims_contradict,
    _descriptions_conflict,
    _detect_internal_candidate_conflicts,
    _is_underintegrated_story_match,
    _normalize_world_name,
    _should_surface_story_item,
    _should_surface_world_item,
    _world_names_equivalent,
    _world_text_mentions_name,
)
from app.utils.world_building_document_utils import (
    list_world_building_documents,
)
from app.utils.world_building_document_workflow_utils import sync_world_document_elements
from app.utils.world_building_note_utils import save_canon_override, save_world_note
from app.utils.world_building_serialization_utils import (
    rank_world_elements_for_query,
    serialize_world_element,
)
from app.utils.world_building_story_utils import (
    collect_story_characters,
    collect_story_elements,
    load_canon_override_lookup,
    load_character_registry,
)
from app.utils.world_building_wiki_utils import build_series_world_context, build_world_context


def classify_world_intent(query: str | None) -> str:
    text = (query or "").strip().lower()
    if any(token in text for token in ("use", "integrate", "where", "thread", "story", "scene")):
        return "story_integration"
    if any(
        token in text
        for token in ("missing", "gap", "incomplete", "contradiction", "consistency", "worldbuild")
    ):
        return "gap_detection"
    return "gap_detection"


async def extract_world_elements(db: AsyncSession, book: Book) -> list[WorldElement]:
    await sync_world_document_elements(db, book)
    rows = list(
        (
            await db.execute(
                select(WorldElement)
                .where(WorldElement.book_id == book.id)
                .order_by(WorldElement.source_scope.asc(), WorldElement.name.asc())
            )
        )
        .scalars()
        .all()
    )
    return rows


async def list_extracted_world_elements(db: AsyncSession, book: Book) -> list[dict]:
    rows = await extract_world_elements(db, book)
    return [serialize_world_element(element) for element in rows]


async def build_world_logic_response(db: AsyncSession, book: Book, query: str, mode: str) -> dict:
    elements = await extract_world_elements(db, book)
    context = build_world_context(elements)
    analysis = (
        await detect_integration_analysis(db, book)
        if mode == "story_integration"
        else await detect_world_gaps(db, book)
    )
    logic_alerts = list((analysis.get("consistency_flags") or [])[:4])
    suggestions = list(
        (analysis.get("integration_opportunities") or analysis.get("priority_gaps") or [])[:5]
    )

    ranked_elements = rank_world_elements_for_query(elements, query)
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
        simulation_steps.append(
            "No direct lore entity matched the query, so the simulator is leaning on broader world context."
        )

    if any(
        token in query.lower()
        for token in ("react", "response", "respond", "kingdom", "court", "faction")
    ):
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


async def ingest_world_elements_from_chapter(
    db: AsyncSession,
    *,
    book: Book,
    chapter: Chapter,
    chapter_text: str,
) -> list[WorldElement]:
    character_registry = await load_character_registry(db, book)
    override_lookup = await load_canon_override_lookup(db, book)
    extracted = _apply_character_and_override_resolution(
        extract_world_elements_from_text(chapter_text, chapter_number=chapter.number),
        character_registry=character_registry,
        override_lookup=override_lookup,
    )
    if not extracted:
        return []

    existing = (
        (
            await db.execute(
                select(WorldElement).where(
                    WorldElement.book_id == book.id,
                    WorldElement.source_scope == "story",
                )
            )
        )
        .scalars()
        .all()
    )
    by_name = {element.name.strip().lower(): element for element in existing if element.name}
    touched: list[WorldElement] = []

    for candidate in extracted:
        key = _normalize_world_name(
            str(candidate.get("canonical_name") or candidate.get("name") or "").strip()
        )
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
                element_type=str(candidate.get("element_type") or "concept"),
                name=str(candidate.get("canonical_name") or candidate.get("name") or "").strip(),
                description=description,
                usage_count=usage_increment,
                dependencies=list(candidate.get("claims") or []),
                analysis_metadata={
                    "source": "chapter_text",
                    "chapter_number": chapter.number,
                    "chapter_title": chapter.title,
                    "canonical_name": str(
                        candidate.get("canonical_name") or candidate.get("name") or ""
                    ).strip(),
                    "aliases": list(candidate.get("aliases") or []),
                    "confidence": float(candidate.get("confidence") or 0.0),
                    "provenance": list(candidate.get("provenance") or []),
                    "claims": list(candidate.get("claims") or []),
                    "chapter_numbers": list(candidate.get("chapter_numbers") or [chapter.number]),
                    "chapter_count": len(candidate.get("chapter_numbers") or [chapter.number]),
                    "presence_score": float(candidate.get("presence_score") or 0.0),
                    "narrative_modes": list(candidate.get("narrative_modes") or []),
                    "source_excerpt": candidate.get("source_excerpt"),
                    "character_id": candidate.get("character_id"),
                    "author_override": bool(candidate.get("author_override")),
                },
                is_series_canonical=bool(book.primary_series_id),
            )
            db.add(current)
            by_name[key] = current
        else:
            current.usage_count = int(current.usage_count or 0) + usage_increment
            if description and (
                not current.description or len(description) > len(current.description)
            ):
                current.description = description
            metadata = dict(current.analysis_metadata or {})
            chapter_numbers = sorted(
                {
                    *(metadata.get("chapter_numbers") or []),
                    *(candidate.get("chapter_numbers") or [chapter.number]),
                }
            )
            metadata.setdefault("chapter_number", chapter.number)
            metadata.setdefault("chapter_title", chapter.title)
            metadata["canonical_name"] = str(
                candidate.get("canonical_name") or current.name or ""
            ).strip()
            metadata["aliases"] = _dedupe_strings(
                [*(metadata.get("aliases") or []), *(candidate.get("aliases") or [])]
            )
            metadata["confidence"] = max(
                float(metadata.get("confidence") or 0.0), float(candidate.get("confidence") or 0.0)
            )
            metadata["provenance"] = [
                *(metadata.get("provenance") or []),
                *(candidate.get("provenance") or []),
            ][:8]
            metadata["claims"] = _merge_claims(
                metadata.get("claims") or [], candidate.get("claims") or []
            )
            metadata["chapter_numbers"] = chapter_numbers
            metadata["chapter_count"] = len(chapter_numbers)
            metadata["presence_score"] = max(
                float(metadata.get("presence_score") or 0.0),
                float(candidate.get("presence_score") or 0.0),
            )
            metadata["narrative_modes"] = _dedupe_strings(
                [
                    *(metadata.get("narrative_modes") or []),
                    *(candidate.get("narrative_modes") or []),
                ]
            )
            metadata["source_excerpt"] = metadata.get("source_excerpt") or candidate.get(
                "source_excerpt"
            )
            metadata["character_id"] = metadata.get("character_id") or candidate.get("character_id")
            metadata["author_override"] = bool(metadata.get("author_override")) or bool(
                candidate.get("author_override")
            )
            current.analysis_metadata = metadata
            current.dependencies = _merge_claims(
                list(current.dependencies or []), list(candidate.get("claims") or [])
            )
        touched.append(current)

    await db.flush()
    return touched


async def detect_world_gaps(db: AsyncSession, book: Book) -> dict:
    documents = await list_world_building_documents(db, book)
    document_elements = await sync_world_document_elements(db, book)
    story_elements = await collect_story_elements(db, book)
    characters = await collect_story_characters(db, book)
    story_candidate_records = await collect_story_candidate_records(db, book)
    world_candidate_records = await collect_world_document_candidate_records(db, book, documents)
    return await build_world_gap_analysis_payload(
        db,
        book_id=book.id,
        series_id=book.primary_series_id,
        mode="gap_detection",
        documents=documents,
        document_elements=document_elements,
        story_elements=story_elements,
        characters=characters,
        story_candidate_records=story_candidate_records,
        world_candidate_records=world_candidate_records,
    )


async def detect_series_world_analysis(db: AsyncSession, series_id: uuid.UUID) -> dict:
    membership_rows = (
        await db.execute(
            select(Book, SeriesBook.position)
            .join(SeriesBook, SeriesBook.book_id == Book.id)
            .where(SeriesBook.series_id == series_id, Book.hidden_at.is_(None))
            .order_by(
                SeriesBook.position.asc().nullslast(), Book.created_at.asc(), Book.title.asc()
            )
        )
    ).all()
    books = [book for book, _ in membership_rows]
    if not books:
        return {
            "series_id": str(series_id),
            "book_count": 0,
            "analysis_count": 0,
            "books": [],
            "world_context": "",
            "gap_analysis": empty_gap_analysis_payload("series_gap_detection"),
            "integration_analysis": empty_integration_analysis_payload("series_story_integration"),
        }

    documents: list[WorldBuildingDocument] = []
    document_elements: list[WorldElement] = []
    story_elements: list[WorldElement] = []
    story_candidate_records: list[dict] = []
    world_candidate_records: list[dict] = []
    characters: list[dict] = []
    books_payload: list[dict] = []

    for book, position in membership_rows:
        book_documents = await list_world_building_documents(db, book)
        documents.extend(book_documents)
        document_elements.extend(await sync_world_document_elements(db, book))
        story_elements.extend(await collect_story_elements(db, book))
        story_candidate_records.extend(await collect_story_candidate_records(db, book))
        world_candidate_records.extend(
            await collect_world_document_candidate_records(db, book, book_documents)
        )
        characters.extend(await collect_story_characters(db, book))
        books_payload.append(
            {
                "book_id": str(book.id),
                "title": book.title,
                "position": position,
                "world_document_count": sum(
                    1 for document in documents if document.book_id == book.id
                ),
            }
        )

    gap_payload = await build_world_gap_analysis_payload(
        db,
        book_id=None,
        series_id=series_id,
        mode="series_gap_detection",
        documents=documents,
        document_elements=document_elements,
        story_elements=story_elements,
        characters=characters,
        story_candidate_records=story_candidate_records,
        world_candidate_records=world_candidate_records,
        consistency_elements=[*document_elements, *story_elements],
        persist=False,
    )
    integration_payload = await build_integration_analysis_payload(
        db,
        book_id=None,
        series_id=series_id,
        mode="series_story_integration",
        documents=documents,
        document_elements=document_elements,
        story_elements=story_elements,
        consistency_elements=[*document_elements, *story_elements],
        persist=False,
    )
    return {
        "series_id": str(series_id),
        "book_count": len(books),
        "analysis_count": 2,
        "books": books_payload,
        "world_context": await build_series_world_context(db, series_id),
        "gap_analysis": gap_payload,
        "integration_analysis": integration_payload,
    }


async def detect_integration_analysis(db: AsyncSession, book: Book) -> dict:
    documents = await list_world_building_documents(db, book)
    document_elements = await sync_world_document_elements(db, book)
    story_elements = await collect_story_elements(db, book)
    return await build_integration_analysis_payload(
        db,
        book_id=book.id,
        series_id=book.primary_series_id,
        mode="story_integration",
        documents=documents,
        document_elements=document_elements,
        story_elements=story_elements,
    )
