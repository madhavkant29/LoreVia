from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book
from app.engine.world.extractor import extract_world_elements_from_text, infer_element_type
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import (
    ChapterSummary,
    WorldCanonicalIdentity,
    WorldElement,
    WorldNote,
)
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS
from app.utils.world_building_candidate_utils import (
    _apply_character_and_override_resolution,
    _dedupe_strings,
    _merge_claims,
    _presence_score,
)
from app.utils.world_building_conflict_utils import _normalize_text, _normalize_world_name

CANON_OVERRIDE_NOTE_TYPE = "canon_override"


async def load_character_registry(db: AsyncSession, book: Book) -> list[dict]:
    rows = (
        await db.execute(
            select(
                Character.id,
                Character.name,
                Character.aliases,
                Character.role,
                Character.first_chapter,
                Character.arc_summary,
                Character.mention_count,
            )
            .where(Character.book_id == book.id)
            .order_by(Character.mention_count.desc(), Character.name.asc())
        )
    ).all()
    registry: list[dict] = []
    for character_id, name, aliases, role, first_chapter, arc_summary, mention_count in rows:
        registry.append(
            {
                "character_id": str(character_id),
                "canonical_name": name,
                "aliases": [alias for alias in (aliases or []) if alias],
                "role": role,
                "first_chapter": first_chapter,
                "arc_summary": arc_summary,
                "mention_count": int(mention_count or 0),
                "entity_type": "character",
            }
        )
    return registry


async def load_canon_override_lookup(db: AsyncSession, book: Book) -> dict[str, dict]:
    identity_rows = (
        (
            await db.execute(
                select(WorldCanonicalIdentity)
                .where(WorldCanonicalIdentity.book_id == book.id)
                .order_by(
                    WorldCanonicalIdentity.updated_at.desc(),
                    WorldCanonicalIdentity.created_at.desc(),
                )
            )
        )
        .scalars()
        .all()
    )
    lookup: dict[str, dict] = {}
    for identity in identity_rows:
        canonical_name = " ".join(str(identity.canonical_name or "").split()).strip()
        if not canonical_name:
            continue
        aliases = [
            " ".join(str(alias or "").split()).strip()
            for alias in (identity.aliases or [])
            if " ".join(str(alias or "").split()).strip()
        ]
        override = {
            "canonical_name": canonical_name,
            "aliases": aliases,
            "entity_type": " ".join(str(identity.entity_type or "").split()).strip() or None,
            "identity_id": str(identity.id),
            "notes": " ".join(str(identity.notes or "").split()).strip() or None,
            "source": identity.source,
            "confidence": float(identity.confidence or 0.0),
        }
        for candidate in [canonical_name, *aliases]:
            key = _normalize_world_name(candidate)
            if key:
                lookup[key] = override

    rows = (
        (
            await db.execute(
                select(WorldNote)
                .where(
                    WorldNote.book_id == book.id, WorldNote.note_type == CANON_OVERRIDE_NOTE_TYPE
                )
                .order_by(WorldNote.updated_at.desc(), WorldNote.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    for note in rows:
        try:
            payload = json.loads(note.body or "{}")
        except json.JSONDecodeError:
            continue
        canonical_name = " ".join(
            str(payload.get("canonical_name") or note.title or "").split()
        ).strip()
        if not canonical_name:
            continue
        aliases = [
            " ".join(str(alias or "").split()).strip()
            for alias in (payload.get("aliases") or [])
            if " ".join(str(alias or "").split()).strip()
        ]
        override = {
            "canonical_name": canonical_name,
            "aliases": aliases,
            "entity_type": " ".join(
                str(payload.get("entity_type") or note.context_label or "").split()
            ).strip()
            or None,
            "note_id": str(note.id),
            "notes": " ".join(str(payload.get("notes") or "").split()).strip() or None,
            "source": "legacy_note",
            "confidence": 0.98,
        }
        for candidate in [canonical_name, *aliases]:
            key = _normalize_world_name(candidate)
            if key and key not in lookup:
                lookup[key] = override
    return lookup


async def apply_summary_mentions(db: AsyncSession, book: Book, collapsed: dict[str, dict]) -> None:
    if not collapsed:
        return
    summary_rows = (
        await db.execute(
            select(Chapter.number, ChapterSummary.content, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id)
        )
    ).all()
    if not summary_rows:
        return
    for chapter_number, content, key_events in summary_rows:
        summary_text_parts = [str(content or "")]
        if isinstance(key_events, list):
            summary_text_parts.extend(
                " ".join(
                    str(event.get(field) or "")
                    for field in ("event_title", "event", "description", "impact")
                    if isinstance(event, dict)
                )
                for event in key_events
                if isinstance(event, dict)
            )
        summary_text = " ".join(part for part in summary_text_parts if part).lower()
        if not summary_text:
            continue
        normalized_summary = _normalize_text(summary_text)
        for item in collapsed.values():
            names = [
                str(item.get("canonical_name") or item.get("name") or "").strip(),
                *[str(alias).strip() for alias in (item.get("aliases") or [])],
            ]
            if any(name and _normalize_world_name(name) in normalized_summary for name in names):
                item["summary_mentions"] = int(item.get("summary_mentions") or 0) + 1
                item["chapter_numbers"] = sorted(
                    {*(item.get("chapter_numbers") or []), chapter_number}
                )


async def collect_story_elements(db: AsyncSession, book: Book) -> list[WorldElement]:
    chapter_rows = (
        await db.execute(
            select(Chapter.id, Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    if not chapter_rows:
        rows = list(
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
        return rows

    character_registry = await load_character_registry(db, book)
    override_lookup = await load_canon_override_lookup(db, book)
    collapsed: dict[str, dict] = {}
    for _, chapter_number, chapter_title, s3_key in chapter_rows:
        if not s3_key:
            continue
        try:
            stored = deserialize_manuscript_content(await asyncio.to_thread(download_book, s3_key))
        except STORAGE_IO_EXCEPTIONS:
            continue
        text = str(stored.get("text") or "")
        normalized_candidates = _apply_character_and_override_resolution(
            extract_world_elements_from_text(text, chapter_number=chapter_number),
            character_registry=character_registry,
            override_lookup=override_lookup,
        )
        for candidate in normalized_candidates:
            name = str(candidate.get("canonical_name") or candidate.get("name") or "").strip()
            if not name:
                continue
            key = _normalize_world_name(name)
            current = collapsed.get(key)
            description = str(candidate.get("description") or "").strip() or None
            usage_count = int(candidate.get("usage_count") or 1)
            if current is None:
                current = {
                    "element_type": str(
                        candidate.get("element_type") or infer_element_type(name, description or "")
                    ),
                    "name": name,
                    "canonical_name": name,
                    "aliases": list(candidate.get("aliases") or []),
                    "description": description,
                    "usage_count": usage_count,
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "chapter_numbers": list(
                        candidate.get("chapter_numbers")
                        or ([chapter_number] if chapter_number else [])
                    ),
                    "confidence": float(candidate.get("confidence") or 0.0),
                    "provenance": list(candidate.get("provenance") or []),
                    "claims": list(candidate.get("claims") or []),
                    "narrative_modes": list(candidate.get("narrative_modes") or []),
                    "summary_mentions": 0,
                    "presence_score": float(candidate.get("presence_score") or 0.0),
                    "source_excerpt": candidate.get("source_excerpt"),
                    "character_id": candidate.get("character_id"),
                    "author_override": bool(candidate.get("author_override")),
                }
                collapsed[key] = current
            else:
                current["usage_count"] = int(current.get("usage_count") or 0) + usage_count
                current["aliases"] = _dedupe_strings(
                    [*(current.get("aliases") or []), *(candidate.get("aliases") or [])]
                )
                current["chapter_numbers"] = sorted(
                    {
                        *(current.get("chapter_numbers") or []),
                        *(candidate.get("chapter_numbers") or [chapter_number]),
                    }
                )
                current["confidence"] = max(
                    float(current.get("confidence") or 0.0),
                    float(candidate.get("confidence") or 0.0),
                )
                current["provenance"] = [
                    *(current.get("provenance") or []),
                    *(candidate.get("provenance") or []),
                ][:8]
                current["claims"] = _merge_claims(
                    current.get("claims") or [], candidate.get("claims") or []
                )
                current["narrative_modes"] = _dedupe_strings(
                    [
                        *(current.get("narrative_modes") or []),
                        *(candidate.get("narrative_modes") or []),
                    ]
                )
                current["character_id"] = current.get("character_id") or candidate.get(
                    "character_id"
                )
                current["author_override"] = bool(current.get("author_override")) or bool(
                    candidate.get("author_override")
                )
                if description and (
                    not current.get("description")
                    or len(description) > len(str(current.get("description") or ""))
                ):
                    current["description"] = description
                    current["source_excerpt"] = candidate.get("source_excerpt")

    await apply_summary_mentions(db, book, collapsed)
    for item in collapsed.values():
        item["presence_score"] = _presence_score(item)

    story_elements: list[WorldElement] = []
    now = datetime.now(UTC)
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
                dependencies=list(item.get("claims") or []),
                analysis_metadata={
                    "source": "chapter_text_snapshot",
                    "chapter_number": item.get("chapter_number"),
                    "chapter_title": item.get("chapter_title"),
                    "canonical_name": item.get("canonical_name"),
                    "aliases": list(item.get("aliases") or []),
                    "confidence": float(item.get("confidence") or 0.0),
                    "provenance": list(item.get("provenance") or []),
                    "claims": list(item.get("claims") or []),
                    "chapter_numbers": list(item.get("chapter_numbers") or []),
                    "chapter_count": len(item.get("chapter_numbers") or []),
                    "summary_mentions": int(item.get("summary_mentions") or 0),
                    "presence_score": float(item.get("presence_score") or 0.0),
                    "narrative_modes": list(item.get("narrative_modes") or []),
                    "source_excerpt": item.get("source_excerpt"),
                    "character_id": item.get("character_id"),
                    "author_override": bool(item.get("author_override")),
                },
                is_series_canonical=bool(book.primary_series_id),
                created_at=now,
                updated_at=now,
            )
        )
    return story_elements


async def collect_story_characters(db: AsyncSession, book: Book) -> list[dict]:
    rows = (
        await db.execute(
            select(
                Character.id,
                Character.name,
                Character.aliases,
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
    for character_id, name, aliases, role, first_chapter, arc_summary, mention_count in rows:
        story_evidence = f"{name} appears in the manuscript"
        if role:
            story_evidence += f" as {role}"
        if arc_summary:
            story_evidence += f". Arc note: {arc_summary[:160]}"
        results.append(
            {
                "id": str(character_id),
                "name": name,
                "aliases": [alias for alias in (aliases or []) if alias],
                "chapter_number": first_chapter,
                "story_evidence": story_evidence,
                "should_watch": int(mention_count or 0) >= 4 or role in {"mc", "sc"},
            }
        )
    return results


def collapse_elements(items: list[dict]) -> dict[str, dict]:
    collapsed: dict[str, dict] = {}
    for item in items:
        key = _normalize_world_name(
            str(item.get("canonical_name") or item.get("name") or "").strip()
        )
        if not key:
            continue
        current = collapsed.get(key)
        if current is None:
            collapsed[key] = dict(item)
            continue
        current["usage_count"] = int(current.get("usage_count") or 0) + int(
            item.get("usage_count") or 0
        )
        current.setdefault("chapter_number", item.get("chapter_number"))
        current.setdefault("chapter_title", item.get("chapter_title"))
        current.setdefault("world_document_id", item.get("world_document_id"))
        current.setdefault("world_document_title", item.get("world_document_title"))
        current["canonical_name"] = (
            current.get("canonical_name") or item.get("canonical_name") or item.get("name")
        )
        current["aliases"] = _dedupe_strings(
            [*(current.get("aliases") or []), *(item.get("aliases") or [])]
        )
        current["confidence"] = max(
            float(current.get("confidence") or 0.0), float(item.get("confidence") or 0.0)
        )
        current["provenance"] = [
            *(current.get("provenance") or []),
            *(item.get("provenance") or []),
        ][:8]
        current["claims"] = _merge_claims(current.get("claims") or [], item.get("claims") or [])
        current["chapter_numbers"] = sorted(
            {*(current.get("chapter_numbers") or []), *(item.get("chapter_numbers") or [])}
        )
        current["chapter_count"] = max(
            int(current.get("chapter_count") or 0), len(current.get("chapter_numbers") or [])
        )
        current["summary_mentions"] = int(current.get("summary_mentions") or 0) + int(
            item.get("summary_mentions") or 0
        )
        current["presence_score"] = max(
            float(current.get("presence_score") or 0.0), float(item.get("presence_score") or 0.0)
        )
        current["narrative_modes"] = _dedupe_strings(
            [*(current.get("narrative_modes") or []), *(item.get("narrative_modes") or [])]
        )
        current["source_excerpt"] = current.get("source_excerpt") or item.get("source_excerpt")
        current["character_id"] = current.get("character_id") or item.get("character_id")
        current["author_override"] = bool(current.get("author_override")) or bool(
            item.get("author_override")
        )
        description = str(item.get("description") or "").strip()
        current_description = str(current.get("description") or "").strip()
        if description and len(description) > len(current_description):
            current["description"] = description
    return collapsed


def apply_gap_scores(elements: list[WorldElement], priority_gaps: list[dict]) -> None:
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


def apply_integration_scores(
    elements: list[WorldElement], integration_opportunities: list[dict]
) -> None:
    by_name = {
        str(item.get("element_name") or "").lower(): item for item in integration_opportunities
    }
    now = datetime.now(UTC)
    for element in elements:
        suggestion_payload = by_name.get(element.name.lower())
        element.integration_score = 0.2 if suggestion_payload else 0.9
        if suggestion_payload:
            element.suggestions = list(suggestion_payload.get("suggestions") or [])
        element.last_integration_analysis = now
