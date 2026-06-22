from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book, upload_binary
from app.engine.character.deduplicator import names_equivalent
from app.engine.world.dependency_graph import build_dependency_graph
from app.engine.world.extractor import (
    extract_claims_from_text,
    extract_world_elements_from_text,
    infer_element_type,
)
from app.engine.world.gap_detector import detect_consistency_flags, detect_gap_categories
from app.models.book import Book, Chapter, SeriesBook
from app.models.character import Character
from app.models.intelligence import (
    ChapterSummary,
    WikiEntry,
    WorldBuildingDocument,
    WorldCanonicalIdentity,
    WorldElement,
    WorldGapAnalysis,
    WorldNote,
)
from app.utils.books.imports import parse_import_upload
from app.utils.books.manuscript import (
    clean_manuscript_html,
    deserialize_manuscript_content,
    serialize_manuscript_content,
)
from app.utils.characters.identity import normalize_character_name
from app.utils.characters.similarity import name_similarity

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
    "coverage_watchlist": (
        "Coverage watchlist",
        "LoreVia keeps a short queue of under-specified canon areas so there are always concrete worldbuilding review targets to tighten.",
    ),
}
CANON_OVERRIDE_NOTE_TYPE = "canon_override"
WORLD_KEEPABLE_TYPES = {
    "character",
    "concept",
    "country",
    "creature",
    "culture",
    "currency",
    "era",
    "event",
    "language",
    "law",
    "magic_system",
    "object",
    "organization",
    "place",
    "politics",
    "power_limit",
    "race",
    "region",
    "religion",
    "technology",
    "travel_rule",
}
WORLD_HIGH_SIGNAL_TYPES = {
    "character",
    "country",
    "currency",
    "law",
    "magic_system",
    "object",
    "organization",
    "place",
    "politics",
    "power_limit",
    "race",
    "region",
    "travel_rule",
}
MIN_WORLD_REVIEW_TARGETS = 3
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
    if any(
        token in text
        for token in ("missing", "gap", "incomplete", "contradiction", "consistency", "worldbuild")
    ):
        return "gap_detection"
    return "gap_detection"


async def _load_character_registry(db: AsyncSession, book: Book) -> list[dict]:
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


async def _load_canon_override_lookup(db: AsyncSession, book: Book) -> dict[str, dict]:
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
        except Exception:
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


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = " ".join((value or "").split()).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _candidate_priority_score(candidate: dict) -> float:
    description = str(candidate.get("description") or "").strip()
    confidence = float(candidate.get("confidence") or 0.0)
    usage_count = int(candidate.get("usage_count") or 0)
    return confidence + min(0.25, usage_count * 0.05) + min(0.2, len(description) / 500.0)


def _normalize_candidate_record(candidate: dict) -> dict:
    canonical_name = " ".join(
        str(candidate.get("canonical_name") or candidate.get("name") or "").split()
    ).strip()
    name = " ".join(str(candidate.get("name") or canonical_name).split()).strip()
    element_type = (
        " ".join(
            str(
                candidate.get("element_type")
                or infer_element_type(name, str(candidate.get("description") or ""))
            ).split()
        )
        .strip()
        .lower()
        or "concept"
    )
    aliases = _dedupe_strings([name, *[str(alias) for alias in (candidate.get("aliases") or [])]])
    description = " ".join(str(candidate.get("description") or "").split()).strip() or None
    chapter_number = candidate.get("chapter_number")
    provenance = (
        candidate.get("provenance") if isinstance(candidate.get("provenance"), dict) else {}
    )
    claims = [claim for claim in (candidate.get("claims") or []) if isinstance(claim, dict)]
    confidence = max(0.05, min(0.99, float(candidate.get("confidence") or 0.35)))
    return {
        "name": canonical_name or name,
        "canonical_name": canonical_name or name,
        "aliases": aliases,
        "element_type": element_type,
        "description": description,
        "usage_count": int(candidate.get("usage_count") or 1),
        "chapter_number": chapter_number,
        "chapter_numbers": [chapter_number] if chapter_number else [],
        "confidence": confidence,
        "claims": claims,
        "provenance": [provenance] if provenance else [],
        "narrative_modes": [str(provenance.get("narrative_mode") or "")] if provenance else [],
        "source_excerpt": str(provenance.get("excerpt") or description or "").strip() or None,
        "character_id": candidate.get("character_id"),
        "author_override": bool(candidate.get("author_override")),
        "summary_mentions": int(candidate.get("summary_mentions") or 0),
        "presence_score": float(candidate.get("presence_score") or 0.0),
    }


def _apply_character_and_override_resolution(
    candidates: list[dict],
    *,
    character_registry: list[dict],
    override_lookup: dict[str, dict],
) -> list[dict]:
    resolved: list[dict] = []
    for candidate in candidates:
        normalized = _normalize_candidate_record(candidate)
        raw_name = normalized["name"]
        override = _resolve_override(raw_name, normalized["aliases"], override_lookup)
        match = _resolve_character_match(raw_name, normalized["aliases"], character_registry)
        if override is not None:
            normalized["canonical_name"] = override["canonical_name"]
            normalized["name"] = override["canonical_name"]
            normalized["aliases"] = _dedupe_strings(
                [
                    *normalized["aliases"],
                    override["canonical_name"],
                    *(override.get("aliases") or []),
                ]
            )
            if override.get("entity_type"):
                normalized["element_type"] = str(override["entity_type"]).strip().lower()
            normalized["author_override"] = True
            normalized["confidence"] = max(float(normalized.get("confidence") or 0.0), 0.96)
        elif match is not None:
            normalized["canonical_name"] = match["canonical_name"]
            normalized["name"] = match["canonical_name"]
            normalized["aliases"] = _dedupe_strings(
                [*normalized["aliases"], match["canonical_name"], *(match.get("aliases") or [])]
            )
            normalized["element_type"] = "character"
            normalized["character_id"] = match["character_id"]
            normalized["confidence"] = max(float(normalized.get("confidence") or 0.0), 0.9)
        resolved.append(normalized)
    return _merge_canonical_candidates(resolved)


def _resolve_override(
    name: str, aliases: list[str], override_lookup: dict[str, dict]
) -> dict | None:
    keys = {_normalize_world_name(name), *(_normalize_world_name(alias) for alias in aliases)}
    keys.discard("")
    for key in keys:
        if key in override_lookup:
            return override_lookup[key]
    for override in override_lookup.values():
        if _world_names_equivalent(name, override.get("canonical_name")):
            return override
    return None


def _resolve_character_match(
    name: str, aliases: list[str], character_registry: list[dict]
) -> dict | None:
    best_match: dict | None = None
    best_score = 0.0
    for character in character_registry:
        canonical_name = str(character.get("canonical_name") or "").strip()
        character_aliases = [
            str(alias) for alias in (character.get("aliases") or []) if str(alias).strip()
        ]
        if not canonical_name:
            continue
        if not names_equivalent(name, aliases, canonical_name, character_aliases):
            continue
        candidate_names = [canonical_name, *character_aliases]
        score = max(
            max(
                (name_similarity(name, candidate_name) for candidate_name in candidate_names),
                default=0.0,
            ),
            max(
                (
                    name_similarity(alias, candidate_name)
                    for alias in aliases
                    for candidate_name in candidate_names
                ),
                default=0.0,
            ),
        )
        if score >= best_score:
            best_score = score
            best_match = character
    return best_match if best_score >= 0.74 else None


def _merge_canonical_candidates(candidates: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for candidate in candidates:
        key = _normalize_world_name(candidate.get("canonical_name") or candidate.get("name") or "")
        if not key:
            continue
        current = merged.get(key)
        if current is None:
            merged[key] = dict(candidate)
            continue
        current["usage_count"] = int(current.get("usage_count") or 0) + int(
            candidate.get("usage_count") or 0
        )
        current["aliases"] = _dedupe_strings(
            [*(current.get("aliases") or []), *(candidate.get("aliases") or [])]
        )
        current["chapter_numbers"] = sorted(
            {*current.get("chapter_numbers", []), *candidate.get("chapter_numbers", [])}
        )
        current["summary_mentions"] = int(current.get("summary_mentions") or 0) + int(
            candidate.get("summary_mentions") or 0
        )
        current["provenance"] = [*current.get("provenance", []), *candidate.get("provenance", [])][
            :8
        ]
        current["narrative_modes"] = _dedupe_strings(
            [*current.get("narrative_modes", []), *candidate.get("narrative_modes", [])]
        )
        current["claims"] = _merge_claims(
            current.get("claims") or [], candidate.get("claims") or []
        )
        current["confidence"] = max(
            float(current.get("confidence") or 0.0), float(candidate.get("confidence") or 0.0)
        )
        current["author_override"] = bool(current.get("author_override")) or bool(
            candidate.get("author_override")
        )
        current["character_id"] = current.get("character_id") or candidate.get("character_id")
        if _candidate_priority_score(candidate) > _candidate_priority_score(current):
            current["description"] = candidate.get("description")
            current["source_excerpt"] = candidate.get("source_excerpt")
            current["element_type"] = candidate.get("element_type") or current.get("element_type")
        elif not current.get("description") and candidate.get("description"):
            current["description"] = candidate.get("description")
            current["source_excerpt"] = candidate.get("source_excerpt")
        current["presence_score"] = max(
            float(current.get("presence_score") or 0.0),
            float(candidate.get("presence_score") or 0.0),
        )

    normalized_items = list(merged.values())
    for item in normalized_items:
        item["presence_score"] = _presence_score(item)
    return sorted(
        normalized_items,
        key=lambda item: (
            -float(item.get("confidence") or 0.0),
            -int(item.get("usage_count") or 0),
            str(item.get("name") or ""),
        ),
    )


def _merge_claims(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], dict] = {}
    for claim in [*existing, *incoming]:
        attribute = " ".join(str(claim.get("attribute") or "").split()).strip().lower()
        value = " ".join(str(claim.get("value") or "").split()).strip().lower()
        if not attribute or not value:
            continue
        key = (attribute, value)
        current = by_key.get(key)
        if current is None or float(claim.get("confidence") or 0.0) > float(
            current.get("confidence") or 0.0
        ):
            by_key[key] = dict(claim)
    return list(by_key.values())


def _presence_score(candidate: dict) -> float:
    usage_count = int(candidate.get("usage_count") or 0)
    chapter_count = len(candidate.get("chapter_numbers") or [])
    summary_mentions = int(candidate.get("summary_mentions") or 0)
    narrative_modes = {mode for mode in (candidate.get("narrative_modes") or []) if mode}
    confidence = float(candidate.get("confidence") or 0.0)
    score = (
        0.15
        + min(0.25, usage_count * 0.06)
        + min(0.25, chapter_count * 0.12)
        + min(0.15, summary_mentions * 0.07)
    )
    score += min(0.15, confidence * 0.15)
    if narrative_modes and narrative_modes == {"dialogue"}:
        score -= 0.12
    if candidate.get("character_id"):
        score += 0.08
    if str(candidate.get("element_type") or "") in WORLD_HIGH_SIGNAL_TYPES:
        score += 0.05
    return max(0.0, min(0.99, round(score, 3)))


async def list_world_building_documents(
    db: AsyncSession,
    book: Book,
    *,
    include_inactive: bool = False,
) -> list[WorldBuildingDocument]:
    stmt = select(WorldBuildingDocument).where(WorldBuildingDocument.book_id == book.id)
    if not include_inactive:
        stmt = stmt.where(WorldBuildingDocument.is_active.is_(True))
    stmt = stmt.order_by(
        WorldBuildingDocument.updated_at.desc(), WorldBuildingDocument.created_at.desc()
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_world_building_document(
    db: AsyncSession,
    book: Book,
    document_id: uuid.UUID,
    *,
    include_inactive: bool = True,
) -> WorldBuildingDocument:
    document = await db.get(WorldBuildingDocument, document_id)
    if (
        not document
        or document.book_id != book.id
        or (not include_inactive and not document.is_active)
    ):
        raise HTTPException(404, "World-building document not found")
    return document


async def load_world_building_document_payload(
    document: WorldBuildingDocument,
) -> dict[str, str | None]:
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
        merged_text = "\n\n".join(
            str(item.get("text") or "").strip()
            for item in parsed
            if str(item.get("text") or "").strip()
        ).strip()
        merged_html = (
            "\n".join(
                str(item.get("html") or "").strip()
                for item in parsed
                if str(item.get("html") or "").strip()
            ).strip()
            or None
        )
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


async def _collect_story_candidate_records(db: AsyncSession, book: Book) -> list[dict]:
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    if not chapter_rows:
        return []

    character_registry = await _load_character_registry(db, book)
    override_lookup = await _load_canon_override_lookup(db, book)
    records: list[dict] = []
    for chapter_number, chapter_title, s3_key in chapter_rows:
        if not s3_key:
            continue
        try:
            stored = deserialize_manuscript_content(download_book(s3_key))
        except Exception:
            continue
        text = str(stored.get("text") or "")
        for candidate in _apply_character_and_override_resolution(
            extract_world_elements_from_text(text, chapter_number=chapter_number),
            character_registry=character_registry,
            override_lookup=override_lookup,
        ):
            candidate_record = dict(candidate)
            candidate_record["chapter_number"] = chapter_number
            candidate_record["chapter_title"] = chapter_title
            records.append(candidate_record)
    return records


async def _collect_world_document_candidate_records(
    db: AsyncSession,
    book: Book,
    documents: list[WorldBuildingDocument],
) -> list[dict]:
    if not documents:
        return []

    character_registry = await _load_character_registry(db, book)
    override_lookup = await _load_canon_override_lookup(db, book)
    records: list[dict] = []
    for document in documents:
        payload = await load_world_building_document_payload(document)
        text = str(payload.get("text") or "")
        for candidate in _apply_character_and_override_resolution(
            extract_world_elements_from_text(text),
            character_registry=character_registry,
            override_lookup=override_lookup,
        ):
            candidate_record = dict(candidate)
            candidate_record["world_document_id"] = str(document.id)
            candidate_record["world_document_title"] = document.title
            records.append(candidate_record)
    return records


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
        title = (
            " ".join(str(payload.get("title") or "").split()).strip() or "Worldbuilding Manuscript"
        )
        html = str(payload.get("html") or "").strip() or None
        serialized = serialize_manuscript_content(text, html).encode("utf-8")
        storage_key = upload_binary(
            f"worldbuilding/{user_id}/{book.id}/{uuid.uuid4()}.json",
            serialized,
            "application/json",
        )
        document = WorldBuildingDocument(
            book_id=book.id,
            title=title,
            source_name=" ".join(str(payload.get("source_name") or "").split()).strip() or None,
            s3_key=storage_key,
            word_count=_count_words(text),
            source_size_bytes=len(serialized),
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

    next_title = (
        " ".join((title or document.title or "").split()).strip() or "Worldbuilding Manuscript"
    )
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
        )
        .scalars()
        .all()
    )
    return rows


async def list_extracted_world_elements(db: AsyncSession, book: Book) -> list[dict]:
    rows = await extract_world_elements(db, book)
    return [_serialize_world_element(element) for element in rows]


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
        (await db.execute(select(WikiEntry).where(WikiEntry.book_id == book.id))).scalars().all()
    )
    by_name = {entry.name.strip().lower(): entry for entry in existing if entry.name}
    touched: list[WikiEntry] = []

    for element in elements:
        key = element.name.strip().lower()
        if not key:
            continue
        metadata = element.analysis_metadata or {}
        entry = by_name.get(key)
        description = (
            element.description or ""
        ).strip() or f"{element.name} appears in the manuscript and has not been summarized yet."
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
            entry.description = (
                description
                if len(description) >= len(entry.description or "")
                else entry.description
            )
            entry.first_mention = entry.first_mention or (
                int(metadata.get("chapter_number") or 0) or None
            )
            entry.related_char_ids = entry.related_char_ids or (character_ids or None)
        touched.append(entry)

    for chapter_number, chapter_title, key_events in summaries:
        if not isinstance(key_events, list):
            continue
        for event in key_events[:3]:
            if not isinstance(event, dict):
                continue
            name = " ".join(
                str(event.get("event_title") or event.get("event") or "").split()
            ).strip()
            if not name:
                continue
            key = name.lower()
            entry = by_name.get(key)
            description = " ".join(
                str(event.get("description") or event.get("impact") or "").split()
            ).strip() or (
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
                entry.description = (
                    description
                    if len(description) >= len(entry.description or "")
                    else entry.description
                )
                entry.first_mention = entry.first_mention or chapter_number
            touched.append(entry)

    await db.flush()
    return sorted(touched, key=lambda item: (item.entry_type, item.name.lower()))


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


async def sync_world_document_elements(db: AsyncSession, book: Book) -> list[WorldElement]:
    documents = await list_world_building_documents(db, book)
    character_registry = await _load_character_registry(db, book)
    override_lookup = await _load_canon_override_lookup(db, book)
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
        raw_candidates = extract_world_elements_from_text(text)
        normalized_candidates = _apply_character_and_override_resolution(
            raw_candidates,
            character_registry=character_registry,
            override_lookup=override_lookup,
        )
        for candidate in normalized_candidates:
            name = str(candidate.get("canonical_name") or candidate.get("name") or "").strip()
            if not name:
                continue
            element = WorldElement(
                book_id=book.id,
                series_id=book.primary_series_id,
                source_book_id=book.id,
                world_document_id=document.id,
                source_scope="worldbuilding",
                element_type=str(
                    candidate.get("element_type")
                    or infer_element_type(name, str(candidate.get("description") or ""))
                ),
                name=name,
                description=str(candidate.get("description") or "").strip() or None,
                usage_count=int(candidate.get("usage_count") or 1),
                dependencies=list(candidate.get("claims") or []),
                analysis_metadata={
                    "source": "world_document",
                    "world_document_title": document.title,
                    "world_document_source_name": document.source_name,
                    "canonical_name": name,
                    "aliases": list(candidate.get("aliases") or []),
                    "confidence": float(candidate.get("confidence") or 0.0),
                    "provenance": list(candidate.get("provenance") or []),
                    "claims": list(candidate.get("claims") or []),
                    "chapter_numbers": list(candidate.get("chapter_numbers") or []),
                    "chapter_count": len(candidate.get("chapter_numbers") or []),
                    "presence_score": float(candidate.get("presence_score") or 0.0),
                    "narrative_modes": list(candidate.get("narrative_modes") or []),
                    "source_excerpt": candidate.get("source_excerpt"),
                    "character_id": candidate.get("character_id"),
                    "author_override": bool(candidate.get("author_override")),
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
    character_registry = await _load_character_registry(db, book)
    override_lookup = await _load_canon_override_lookup(db, book)
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
        (await db.execute(select(SeriesBook.book_id).where(SeriesBook.series_id == series_id)))
        .scalars()
        .all()
    )
    if not book_ids:
        return ""
    elements = list(
        (await db.execute(select(WorldElement).where(WorldElement.book_id.in_(book_ids))))
        .scalars()
        .all()
    )
    return build_world_context(elements)


async def detect_world_gaps(db: AsyncSession, book: Book) -> dict:
    documents = await list_world_building_documents(db, book)
    document_elements = await sync_world_document_elements(db, book)
    story_elements = await _collect_story_elements(db, book)
    characters = await _collect_story_characters(db, book)
    story_candidate_records = await _collect_story_candidate_records(db, book)
    world_candidate_records = await _collect_world_document_candidate_records(db, book, documents)
    return await _build_world_gap_analysis_payload(
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
            "gap_analysis": _empty_gap_analysis_payload("series_gap_detection"),
            "integration_analysis": _empty_integration_analysis_payload("series_story_integration"),
        }

    documents: list[WorldBuildingDocument] = []
    document_elements: list[WorldElement] = []
    story_elements: list[WorldElement] = []
    characters: list[dict] = []
    books_payload: list[dict] = []

    for book, position in membership_rows:
        documents.extend(await list_world_building_documents(db, book))
        document_elements.extend(await sync_world_document_elements(db, book))
        story_elements.extend(await _collect_story_elements(db, book))
        characters.extend(await _collect_story_characters(db, book))
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

    gap_payload = await _build_world_gap_analysis_payload(
        db,
        book_id=None,
        series_id=series_id,
        mode="series_gap_detection",
        documents=documents,
        document_elements=document_elements,
        story_elements=story_elements,
        characters=characters,
        consistency_elements=[*document_elements, *story_elements],
        persist=False,
    )
    integration_payload = await _build_integration_analysis_payload(
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


def _empty_gap_analysis_payload(mode: str) -> dict:
    return {
        "mode": mode,
        "generated_at": None,
        "gap_categories": {},
        "gap_groups": [],
        "priority_gaps": [],
        "consistency_flags": [],
        "world_elements": [],
        "world_documents": [],
    }


def _empty_integration_analysis_payload(mode: str) -> dict:
    return {
        "mode": mode,
        "generated_at": None,
        "integration_opportunities": [],
        "consistency_flags": [],
        "world_elements": [],
        "world_documents": [],
        "dependency_graph": [],
    }


async def _build_world_gap_analysis_payload(
    db: AsyncSession,
    *,
    book_id: uuid.UUID | None,
    series_id: uuid.UUID | None,
    mode: str,
    documents: list[WorldBuildingDocument],
    document_elements: list[WorldElement],
    story_elements: list[WorldElement],
    characters: list[dict],
    story_candidate_records: list[dict] | None = None,
    world_candidate_records: list[dict] | None = None,
    consistency_elements: list[WorldElement] | None = None,
    persist: bool = True,
) -> dict:
    story_by_name = _collapse_elements([_serialize_world_element(item) for item in story_elements])
    world_by_name = _collapse_elements(
        [_serialize_world_element(item) for item in document_elements]
    )
    world_corpus_text = "\n".join(
        f"{item.get('canonical_name') or item.get('name') or ''} {' '.join(item.get('aliases') or [])} {item.get('description') or ''}"
        for item in world_by_name.values()
    ).lower()

    grouped_items: dict[str, list[dict]] = defaultdict(list)
    for item in _detect_internal_candidate_conflicts(
        world_candidate_records or [], source_kind="world"
    ):
        grouped_items["story_conflicts"].append(item)
    for item in _detect_internal_candidate_conflicts(
        story_candidate_records or [], source_kind="story"
    ):
        grouped_items["story_conflicts"].append(item)

    for key, world_item in world_by_name.items():
        if not _should_surface_world_item(world_item):
            continue
        story_match = _find_matching_item(
            world_item["name"], story_by_name, aliases=world_item.get("aliases") or []
        )
        if story_match is None:
            grouped_items["missing_in_story"].append(
                _build_gap_item(
                    category="missing_in_story",
                    severity="high",
                    title=f"{world_item['name']} is missing from the story manuscript",
                    description="This lore item is documented in the world-building corpus but does not appear in the current story manuscript.",
                    suggested_fix=f"Seed {world_item['name']} into a chapter scene, summary beat, or character conversation so the manuscript reflects the reference lore.",
                    world_item=world_item,
                    priority=8
                    if str(world_item.get("element_type") or "") in WORLD_HIGH_SIGNAL_TYPES
                    else 6,
                )
            )
            continue

        conflict_detail = _build_cross_source_conflict_detail(world_item, story_match)
        if conflict_detail is not None:
            grouped_items["story_conflicts"].append(
                _build_gap_item(
                    category="story_conflicts",
                    severity="critical",
                    title=conflict_detail["title"],
                    description=conflict_detail["description"],
                    suggested_fix=conflict_detail["suggested_fix"],
                    world_item=world_item,
                    story_item=story_match,
                    priority=10,
                    world_evidence=conflict_detail.get("world_evidence"),
                    story_evidence=conflict_detail.get("story_evidence"),
                )
            )
            continue

        if _is_underintegrated_story_match(story_match):
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
        if _find_matching_item(
            story_item["name"], world_by_name, aliases=story_item.get("aliases") or []
        ) is not None or not _should_surface_story_item(story_item):
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
        character_aliases = list(character.get("aliases") or [])
        if (
            _world_text_mentions_name(world_corpus_text, character["name"])
            or any(
                _world_text_mentions_name(world_corpus_text, alias) for alias in character_aliases
            )
            or _find_matching_item(character["name"], world_by_name, aliases=character_aliases)
            is not None
        ):
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
        ordered_items = sorted(
            items, key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or ""))
        )
        gap_groups.append(
            {
                "key": key,
                "label": label,
                "description": description,
                "items": ordered_items,
            }
        )
    gap_groups.sort(
        key=lambda item: max(
            (int(entry.get("priority") or 0) for entry in item["items"]), default=0
        ),
        reverse=True,
    )

    gap_categories = {group["key"]: group["items"] for group in gap_groups}
    priority_gaps = [item for group in gap_groups for item in group["items"]]
    priority_gaps.sort(
        key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or ""))
    )
    consistency_flags = detect_consistency_flags(
        [_serialize_world_element(item) for item in (consistency_elements or document_elements)]
    )
    supplemental_needed = max(
        0, MIN_WORLD_REVIEW_TARGETS - (len(priority_gaps) + len(consistency_flags))
    )
    if supplemental_needed:
        supplemental_items = _build_coverage_watchlist_items(
            story_by_name=story_by_name,
            world_by_name=world_by_name,
            characters=characters,
            limit=supplemental_needed,
            existing_items=priority_gaps,
        )
        if supplemental_items:
            grouped_items["coverage_watchlist"].extend(supplemental_items)
            gap_groups = []
            for key, items in grouped_items.items():
                label, description = GAP_GROUP_META.get(key, (key.replace("_", " ").title(), None))
                ordered_items = sorted(
                    items,
                    key=lambda item: (
                        -int(item.get("priority") or 0),
                        str(item.get("title") or ""),
                    ),
                )
                gap_groups.append(
                    {
                        "key": key,
                        "label": label,
                        "description": description,
                        "items": ordered_items,
                    }
                )
            gap_groups.sort(
                key=lambda item: max(
                    (int(entry.get("priority") or 0) for entry in item["items"]), default=0
                ),
                reverse=True,
            )
            gap_categories = {group["key"]: group["items"] for group in gap_groups}
            priority_gaps = [item for group in gap_groups for item in group["items"]]
            priority_gaps.sort(
                key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or ""))
            )
    priority_gaps = priority_gaps[:12]

    generated_at = datetime.now(UTC)
    if persist:
        analysis = await _upsert_world_analysis(
            db,
            book_id=book_id,
            series_id=series_id,
            mode=mode,
            gap_categories=gap_categories,
            priority_gaps=priority_gaps,
            integration_opportunities=[],
            consistency_flags=consistency_flags,
        )
        generated_at = analysis.generated_at
    _apply_gap_scores(document_elements, priority_gaps)

    return {
        "mode": mode,
        "generated_at": generated_at,
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
    return await _build_integration_analysis_payload(
        db,
        book_id=book.id,
        series_id=book.primary_series_id,
        mode="story_integration",
        documents=documents,
        document_elements=document_elements,
        story_elements=story_elements,
    )


async def _build_integration_analysis_payload(
    db: AsyncSession,
    *,
    book_id: uuid.UUID | None,
    series_id: uuid.UUID | None,
    mode: str,
    documents: list[WorldBuildingDocument],
    document_elements: list[WorldElement],
    story_elements: list[WorldElement],
    consistency_elements: list[WorldElement] | None = None,
    persist: bool = True,
) -> dict:
    story_by_name = _collapse_elements([_serialize_world_element(item) for item in story_elements])
    integration_opportunities: list[dict] = []

    for element in document_elements:
        serialized_element = _serialize_world_element(element)
        if not _should_surface_world_item(serialized_element):
            continue
        metadata = element.analysis_metadata or {}
        story_match = _find_matching_item(
            element.name,
            story_by_name,
            aliases=metadata.get("aliases") or [],
        )
        story_match_data = story_match or {}
        presence_score = float(story_match_data.get("presence_score") or 0.0)
        usage_count = int(story_match_data.get("usage_count") or 0)
        if presence_score >= 0.62 or usage_count >= 3:
            continue
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
                "priority": 8 if usage_count == 0 else (7 if presence_score < 0.35 else 6),
                "world_document_id": str(element.world_document_id)
                if element.world_document_id
                else None,
                "world_document_title": metadata.get("world_document_title"),
                "confidence": float(serialized_element.get("confidence") or 0.0),
                "canonical_name": serialized_element.get("canonical_name") or element.name,
            }
        )

    integration_opportunities.sort(
        key=lambda item: (-int(item.get("priority") or 0), item["element_name"].lower())
    )
    consistency_flags = detect_consistency_flags(
        [_serialize_world_element(item) for item in (consistency_elements or document_elements)]
    )
    generated_at = datetime.now(UTC)
    if persist:
        analysis = await _upsert_world_analysis(
            db,
            book_id=book_id,
            series_id=series_id,
            mode=mode,
            gap_categories={},
            priority_gaps=[],
            integration_opportunities=integration_opportunities,
            consistency_flags=consistency_flags,
        )
        generated_at = analysis.generated_at
    _apply_integration_scores(document_elements, integration_opportunities)
    return {
        "mode": mode,
        "generated_at": generated_at,
        "integration_opportunities": integration_opportunities,
        "consistency_flags": consistency_flags,
        "world_elements": [_serialize_world_element(element) for element in document_elements],
        "world_documents": [_serialize_world_document(document) for document in documents],
        "dependency_graph": build_dependency_graph(
            [_serialize_world_element(element) for element in document_elements]
        ),
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


async def save_canon_override(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book: Book,
    canonical_name: str,
    aliases: list[str],
    entity_type: str | None = None,
    notes: str | None = None,
) -> WorldCanonicalIdentity:
    cleaned_canonical = " ".join((canonical_name or "").split()).strip()
    if not cleaned_canonical:
        raise HTTPException(400, "Canonical name is required")
    cleaned_aliases = _dedupe_strings(
        [alias for alias in aliases if alias and " ".join(alias.split()).strip()]
    )
    normalized_entity_type = " ".join((entity_type or "").split()).strip() or None
    normalized_notes = " ".join((notes or "").split()).strip() or None

    existing_rows = (
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
    for identity in existing_rows:
        existing_canonical = " ".join(str(identity.canonical_name or "").split()).strip()
        existing_aliases = [
            str(alias).strip() for alias in (identity.aliases or []) if str(alias).strip()
        ]
        if _world_names_equivalent(cleaned_canonical, existing_canonical) or any(
            _world_names_equivalent(alias, cleaned_canonical) for alias in existing_aliases
        ):
            identity.canonical_name = cleaned_canonical
            identity.entity_type = normalized_entity_type
            identity.aliases = _dedupe_strings([*existing_aliases, *cleaned_aliases])
            identity.notes = normalized_notes
            identity.source = "author_override"
            identity.confidence = 0.99
            metadata = dict(identity.metadata_json or {})
            metadata["updated_by_user_id"] = str(user_id)
            identity.metadata_json = metadata
            identity.updated_at = datetime.now(UTC)
            await db.flush()
            return identity

    identity = WorldCanonicalIdentity(
        book_id=book.id,
        canonical_name=cleaned_canonical,
        entity_type=normalized_entity_type,
        aliases=cleaned_aliases or None,
        source="author_override",
        confidence=0.99,
        notes=normalized_notes,
        metadata_json={"created_by_user_id": str(user_id)},
    )
    db.add(identity)
    await db.flush()
    return identity


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
    quality_flags = list(metadata.get("quality_flags") or [])
    grounding_passage_count = int(metadata.get("grounding_passage_count") or 0)
    confidence = metadata.get("confidence")
    if metadata.get("confidence_band"):
        confidence_band = metadata.get("confidence_band")
    elif isinstance(confidence, (int, float)):
        confidence_band = (
            "high"
            if float(confidence) >= 0.85
            else ("medium" if float(confidence) >= 0.6 else "low")
        )
    else:
        confidence_band = None
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
        "canonical_name": metadata.get("canonical_name") or element.name,
        "aliases": list(metadata.get("aliases") or []),
        "confidence": metadata.get("confidence"),
        "provenance": list(metadata.get("provenance") or []),
        "claims": list(metadata.get("claims") or []),
        "chapter_numbers": list(
            metadata.get("chapter_numbers")
            or ([] if metadata.get("chapter_number") is None else [metadata.get("chapter_number")])
        ),
        "chapter_count": metadata.get("chapter_count")
        or (1 if metadata.get("chapter_number") else 0),
        "summary_mentions": metadata.get("summary_mentions") or 0,
        "presence_score": metadata.get("presence_score"),
        "narrative_modes": list(metadata.get("narrative_modes") or []),
        "source_excerpt": metadata.get("source_excerpt"),
        "character_id": metadata.get("character_id"),
        "author_override": bool(metadata.get("author_override")),
        "quality_flags": quality_flags,
        "grounding_passage_count": grounding_passage_count,
        "confidence_band": confidence_band,
    }


async def _apply_summary_mentions(db: AsyncSession, book: Book, collapsed: dict[str, dict]) -> None:
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


async def _collect_story_elements(db: AsyncSession, book: Book) -> list[WorldElement]:
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

    character_registry = await _load_character_registry(db, book)
    override_lookup = await _load_canon_override_lookup(db, book)
    collapsed: dict[str, dict] = {}
    for _, chapter_number, chapter_title, s3_key in chapter_rows:
        if not s3_key:
            continue
        try:
            stored = deserialize_manuscript_content(download_book(s3_key))
        except Exception:
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

    await _apply_summary_mentions(db, book, collapsed)
    for item in collapsed.values():
        item["presence_score"] = _presence_score(item)

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


def _map_element_to_wiki_type(element_type: str) -> str:
    normalized = " ".join((element_type or "").split()).strip().lower()
    if normalized in {
        "place",
        "geography",
        "location",
        "city",
        "country",
        "kingdom",
        "realm",
        "region",
        "territory",
        "province",
    }:
        return "location"
    if normalized in {
        "organization",
        "faction",
        "religion",
        "culture",
        "government",
        "politics",
        "law",
        "race",
        "species",
        "people",
    }:
        return "faction"
    if normalized in {"object", "artifact", "item", "technology", "weapon", "currency"}:
        return "item"
    if normalized in {"event", "history"}:
        return "event"
    return "concept"


def _rank_world_elements_for_query(elements: list[WorldElement], query: str) -> list[WorldElement]:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9']+", (query or "").lower())
        if token not in STOPWORDS
    }

    def score(element: WorldElement) -> tuple[int, int, str]:
        metadata = element.analysis_metadata or {}
        aliases = " ".join(str(alias) for alias in (metadata.get("aliases") or []))
        haystack = (
            f"{element.name} {aliases} {element.description or ''} {element.element_type}".lower()
        )
        overlap = sum(1 for token in tokens if token in haystack)
        return (overlap, int(element.usage_count or 0), element.name.lower())

    return sorted(elements, key=score, reverse=True)


def _collapse_elements(items: list[dict]) -> dict[str, dict]:
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


def _find_matching_item(
    name: str, items_by_name: dict[str, dict], *, aliases: list[str] | None = None
) -> dict | None:
    query_names = [str(name or "").strip(), *[str(alias).strip() for alias in (aliases or [])]]
    query_names = [query_name for query_name in query_names if query_name]
    normalized_keys = {_normalize_world_name(query_name) for query_name in query_names}
    normalized_keys.discard("")
    if not normalized_keys:
        return None

    for key in normalized_keys:
        exact_match = items_by_name.get(key)
        if exact_match is not None:
            return exact_match

    best_match: dict | None = None
    best_score = 0.0
    for candidate in items_by_name.values():
        candidate_names = [
            str(candidate.get("canonical_name") or candidate.get("name") or "").strip(),
            *[str(alias).strip() for alias in (candidate.get("aliases") or [])],
        ]
        candidate_names = [candidate_name for candidate_name in candidate_names if candidate_name]
        if not candidate_names:
            continue
        if any(
            _normalize_world_name(candidate_name) in normalized_keys
            for candidate_name in candidate_names
        ):
            return candidate
        score = max(
            (
                name_similarity(query_name, candidate_name)
                for query_name in query_names
                for candidate_name in candidate_names
                if _world_names_equivalent(query_name, candidate_name)
            ),
            default=0.0,
        )
        if score >= best_score:
            best_score = score
            best_match = candidate
    return best_match if best_score >= 0.84 else None


def _world_names_equivalent(left: str | None, right: str | None) -> bool:
    left_normalized = _normalize_world_name(left)
    right_normalized = _normalize_world_name(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    if names_equivalent(left, [], right, []):
        return True
    return name_similarity(left, right) >= 0.9


def _normalize_world_name(name: str | None) -> str:
    normalized = normalize_character_name(name)
    if normalized:
        return normalized
    return " ".join(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", name or "")).strip().lower()


def _world_text_mentions_name(world_text: str, name: str) -> bool:
    normalized_name = _normalize_world_name(name)
    if not normalized_name:
        return False
    if normalized_name in world_text:
        return True
    world_tokens = set(re.findall(r"[a-z0-9']+", world_text))
    name_tokens = [token for token in normalized_name.split() if token]
    return bool(name_tokens) and set(name_tokens).issubset(world_tokens)


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
    world_evidence: str | None = None,
    story_evidence: str | None = None,
) -> dict:
    if world_item is not None:
        item_name = str(world_item.get("name") or "")
        resolved_world_evidence = (
            world_evidence or str(world_item.get("description") or "").strip() or None
        )
        world_document_id = str(world_item.get("world_document_id") or "") or None
        world_document_title = str(world_item.get("world_document_title") or "").strip() or None
    else:
        item_name = str(story_item.get("name") or "") if story_item else ""
        resolved_world_evidence = world_evidence
        world_document_id = None
        world_document_title = None
    if story_item is not None:
        resolved_story_evidence = (
            story_evidence or str(story_item.get("description") or "").strip() or None
        )
        story_chapter_number = int(story_item.get("chapter_number") or 0) or None
        story_chapter_title = str(story_item.get("chapter_title") or "").strip() or None
    else:
        resolved_story_evidence = story_evidence
        story_chapter_number = None
        story_chapter_title = None
    return {
        "id": f"{category}-{item_name.lower().replace(' ', '-')}",
        "category": category,
        "severity": severity,
        "title": title,
        "description": description,
        "suggested_fix": suggested_fix,
        "world_evidence": resolved_world_evidence,
        "story_evidence": resolved_story_evidence,
        "world_document_id": world_document_id,
        "world_document_title": world_document_title,
        "story_chapter_number": story_chapter_number,
        "story_chapter_title": story_chapter_title,
        "character_name": None,
        "priority": priority,
        "entity_type": str((world_item or story_item or {}).get("element_type") or ""),
        "canonical_name": str((world_item or story_item or {}).get("canonical_name") or item_name),
        "confidence": max(
            float((world_item or {}).get("confidence") or 0.0),
            float((story_item or {}).get("confidence") or 0.0),
        ),
        "provenance": {
            "world": list((world_item or {}).get("provenance") or [])[:2],
            "story": list((story_item or {}).get("provenance") or [])[:2],
        },
    }


def _build_coverage_watchlist_items(
    *,
    story_by_name: dict[str, dict],
    world_by_name: dict[str, dict],
    characters: list[dict],
    limit: int,
    existing_items: list[dict],
) -> list[dict]:
    if limit <= 0:
        return []

    existing_ids = {str(item.get("id") or "") for item in existing_items}
    existing_titles = {str(item.get("title") or "").strip().lower() for item in existing_items}
    supplemental: list[dict] = []

    def add_candidate(item: dict | None) -> None:
        if item is None:
            return
        item_id = str(item.get("id") or "")
        item_title = str(item.get("title") or "").strip().lower()
        if not item_id or item_id in existing_ids or item_title in existing_titles:
            return
        existing_ids.add(item_id)
        existing_titles.add(item_title)
        supplemental.append(item)

    for world_item in sorted(
        world_by_name.values(),
        key=lambda item: (
            int(item.get("usage_count") or 0),
            float(item.get("confidence") or 0.0),
            str(item.get("name") or "").lower(),
        ),
        reverse=True,
    ):
        if len(supplemental) >= limit:
            break
        if not _should_surface_world_item(world_item):
            continue
        description = str(world_item.get("description") or "").strip()
        claims = list(world_item.get("claims") or [])
        provenance = list(world_item.get("provenance") or [])
        story_match = _find_matching_item(
            world_item["name"], story_by_name, aliases=world_item.get("aliases") or []
        )
        if len(description) < 90 or (not claims and len(provenance) < 2):
            add_candidate(
                _build_gap_item(
                    category="coverage_watchlist",
                    severity="low",
                    title=f"{world_item['name']} needs a clearer canon note",
                    description="This lore is present in the active world corpus, but the canon detail is still thin for continuity checks and later retrieval.",
                    suggested_fix=f"Expand {world_item['name']} with stable facts, limits, relationships, and consequences so later chapters can reuse the same canon cleanly.",
                    world_item=world_item,
                    story_item=story_match,
                    priority=4,
                )
            )
        if len(supplemental) >= limit:
            break
        if story_match is not None:
            chapter_count = int(
                story_match.get("chapter_count") or len(story_match.get("chapter_numbers") or [])
            )
            presence_score = float(story_match.get("presence_score") or 0.0)
            if chapter_count <= 1 or presence_score < 0.75:
                add_candidate(
                    _build_gap_item(
                        category="coverage_watchlist",
                        severity="low",
                        title=f"{world_item['name']} needs one more story anchor",
                        description="The canon exists, but the manuscript still gives readers only light runway for this world element.",
                        suggested_fix=f"Reinforce {world_item['name']} in one earlier scene, summary beat, or dialogue exchange so readers can track it before later payoff.",
                        world_item=world_item,
                        story_item=story_match,
                        priority=4,
                    )
                )

    for story_item in sorted(
        story_by_name.values(),
        key=lambda item: (
            int(item.get("usage_count") or 0),
            float(item.get("presence_score") or 0.0),
            str(item.get("name") or "").lower(),
        ),
        reverse=True,
    ):
        if len(supplemental) >= limit:
            break
        if (
            _find_matching_item(
                story_item["name"], world_by_name, aliases=story_item.get("aliases") or []
            )
            is not None
        ):
            continue
        if (
            int(story_item.get("usage_count") or 0) < 2
            and float(story_item.get("confidence") or 0.0) < 0.55
        ):
            continue
        add_candidate(
            _build_gap_item(
                category="coverage_watchlist",
                severity="medium",
                title=f"{story_item['name']} deserves a world note",
                description="This lore is active enough in the manuscript that it is worth pinning down in the canon workspace, even before it becomes a hard contradiction.",
                suggested_fix=f"Create a short worldbuilding note for {story_item['name']} with a stable definition, affected characters, and any rules readers need to remember.",
                story_item=story_item,
                priority=5,
            )
        )

    for character in characters:
        if len(supplemental) >= limit:
            break
        if not character.get("should_watch"):
            continue
        world_match = _find_matching_item(
            str(character.get("name") or ""),
            world_by_name,
            aliases=list(character.get("aliases") or []),
        )
        if world_match is not None:
            continue
        add_candidate(
            {
                "id": f"coverage-watch-character-{character['id']}",
                "category": "coverage_watchlist",
                "severity": "medium",
                "title": f"{character['name']} needs a canon-facing reference note",
                "description": "This character is carrying enough story weight that the worldbuilding workspace should track how lore, factions, or rules interact with them.",
                "suggested_fix": f"Add a concise canon note for {character['name']} covering role, affiliations, pressures, and any world rules tied to their arc.",
                "world_evidence": None,
                "story_evidence": character.get("story_evidence"),
                "world_document_id": None,
                "world_document_title": None,
                "story_chapter_number": character.get("chapter_number"),
                "story_chapter_title": None,
                "character_name": character.get("name"),
                "priority": 4,
                "entity_type": "character",
                "canonical_name": character.get("name"),
                "confidence": 0.0,
                "provenance": {"world": [], "story": []},
            }
        )

    if len(supplemental) < limit:
        baseline_candidates = detect_gap_categories(
            [*world_by_name.values(), *story_by_name.values()]
        )
        for category, items in baseline_candidates.items():
            if len(supplemental) >= limit:
                break
            for item in items:
                if len(supplemental) >= limit:
                    break
                add_candidate(
                    {
                        "id": f"coverage-watch-{category}",
                        "category": "coverage_watchlist",
                        "severity": "low",
                        "title": str(
                            item.get("title") or f"Missing {category.replace('_', ' ')} coverage"
                        ),
                        "description": f"LoreVia could not find a stable {category.replace('_', ' ')} reference layer in the extracted canon, which makes future continuity checks thinner.",
                        "suggested_fix": f"Add or expand notes that clarify the story's {category.replace('_', ' ')} frame, even if the answer is intentionally minimal.",
                        "world_evidence": None,
                        "story_evidence": None,
                        "world_document_id": None,
                        "world_document_title": None,
                        "story_chapter_number": None,
                        "story_chapter_title": None,
                        "character_name": None,
                        "priority": 3,
                        "entity_type": category,
                        "canonical_name": None,
                        "confidence": 0.0,
                        "provenance": {"world": [], "story": []},
                    }
                )

    return supplemental[:limit]


def _should_surface_world_item(world_item: dict) -> bool:
    element_type = str(world_item.get("element_type") or "")
    confidence = float(world_item.get("confidence") or 0.0)
    usage_count = int(world_item.get("usage_count") or 0)
    if element_type not in WORLD_KEEPABLE_TYPES:
        return False
    if confidence < 0.5 and usage_count < 2:
        return False
    return True


def _should_surface_story_item(story_item: dict) -> bool:
    element_type = str(story_item.get("element_type") or "")
    usage_count = int(story_item.get("usage_count") or 0)
    chapter_count = int(
        story_item.get("chapter_count") or len(story_item.get("chapter_numbers") or [])
    )
    presence_score = float(story_item.get("presence_score") or 0.0)
    confidence = float(story_item.get("confidence") or 0.0)
    if element_type not in WORLD_KEEPABLE_TYPES:
        return False
    if presence_score >= 0.62:
        return True
    if usage_count >= 3 and chapter_count >= 2 and confidence >= 0.58:
        return True
    return False


def _is_underintegrated_story_match(story_item: dict) -> bool:
    presence_score = float(story_item.get("presence_score") or 0.0)
    usage_count = int(story_item.get("usage_count") or 0)
    chapter_count = int(
        story_item.get("chapter_count") or len(story_item.get("chapter_numbers") or [])
    )
    return presence_score < 0.58 or usage_count <= 1 or chapter_count <= 1


def _detect_internal_candidate_conflicts(records: list[dict], *, source_kind: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        normalized_name = _normalize_world_name(
            str(record.get("canonical_name") or record.get("name") or "")
        )
        if not normalized_name:
            continue
        grouped[normalized_name].append(record)

    items: list[dict] = []
    for candidates in grouped.values():
        if len(candidates) < 2:
            continue
        ordered = sorted(
            candidates,
            key=lambda item: (
                int(item.get("chapter_number") or 0),
                str(item.get("world_document_title") or ""),
                str(item.get("description") or ""),
            ),
        )
        conflict_detail: dict | None = None
        for index, left_item in enumerate(ordered):
            for right_item in ordered[index + 1 :]:
                if _same_source_reference(left_item, right_item, source_kind=source_kind):
                    continue
                conflict_detail = _build_internal_conflict_detail(
                    left_item, right_item, source_kind=source_kind
                )
                if conflict_detail is not None:
                    break
            if conflict_detail is not None:
                break
        if conflict_detail is not None:
            items.append(conflict_detail)
    return items


def _same_source_reference(left_item: dict, right_item: dict, *, source_kind: str) -> bool:
    if source_kind == "story":
        return int(left_item.get("chapter_number") or 0) == int(
            right_item.get("chapter_number") or 0
        )
    return str(left_item.get("world_document_id") or "") == str(
        right_item.get("world_document_id") or ""
    )


def _build_internal_conflict_detail(
    left_item: dict, right_item: dict, *, source_kind: str
) -> dict | None:
    name = str(
        left_item.get("canonical_name") or left_item.get("name") or right_item.get("name") or ""
    ).strip()
    left_claims = _claims_by_attribute(left_item.get("claims") or [])
    right_claims = _claims_by_attribute(right_item.get("claims") or [])
    for attribute, attribute_left_claims in left_claims.items():
        attribute_right_claims = right_claims.get(attribute) or []
        for left_claim in attribute_left_claims:
            for right_claim in attribute_right_claims:
                if _claims_contradict(left_claim, right_claim):
                    detail = _build_conflict_detail(
                        name,
                        left_item,
                        right_item,
                        left_claim,
                        right_claim,
                        source_kind=source_kind,
                    )
                    detail["id"] = f"story_conflicts-{_normalize_world_name(name)}-{source_kind}"
                    return detail
    if not _descriptions_conflict(
        str(left_item.get("description") or ""), str(right_item.get("description") or "")
    ):
        return None
    left_label = _source_label(left_item, source_kind=source_kind)
    right_label = _source_label(right_item, source_kind=source_kind)
    return {
        "id": f"story_conflicts-{_normalize_world_name(name)}-{source_kind}",
        "category": "story_conflicts",
        "severity": "critical",
        "title": f"{name} conflicts across the {'manuscript' if source_kind == 'story' else 'world notes'}",
        "description": f"{name} is described differently in {left_label} and {right_label}.",
        "suggested_fix": f"Choose the canonical version of {name} and revise the conflicting {'chapter' if source_kind == 'story' else 'worldbuilding note'} so both references align.",
        "world_evidence": _best_evidence_text(left_item),
        "story_evidence": _best_evidence_text(right_item),
        "world_document_id": str(left_item.get("world_document_id") or "") or None,
        "world_document_title": str(left_item.get("world_document_title") or "") or None,
        "story_chapter_number": int(right_item.get("chapter_number") or 0) or None,
        "story_chapter_title": str(right_item.get("chapter_title") or "") or None,
        "character_name": None,
        "priority": 10,
        "entity_type": str(left_item.get("element_type") or right_item.get("element_type") or ""),
        "canonical_name": name,
        "confidence": max(
            float(left_item.get("confidence") or 0.0), float(right_item.get("confidence") or 0.0)
        ),
        "provenance": {
            "world": list(left_item.get("provenance") or [])[:2],
            "story": list(right_item.get("provenance") or [])[:2],
        },
    }


def _build_cross_source_conflict_detail(world_item: dict, story_item: dict) -> dict | None:
    world_claims = _claims_by_attribute(world_item.get("claims") or [])
    story_claims = _claims_by_attribute(story_item.get("claims") or [])
    if world_claims and story_claims:
        for attribute, left_claims in world_claims.items():
            right_claims = story_claims.get(attribute) or []
            if not right_claims:
                continue
            for left_claim in left_claims:
                for right_claim in right_claims:
                    if _claims_contradict(left_claim, right_claim):
                        return _build_conflict_detail(
                            str(world_item.get("name") or ""),
                            world_item,
                            story_item,
                            left_claim,
                            right_claim,
                            source_kind="cross_source",
                        )
        return None

    if not _descriptions_conflict(
        str(world_item.get("description") or ""), str(story_item.get("description") or "")
    ):
        return None
    return {
        "title": f"{world_item['name']} conflicts with the story manuscript",
        "description": "The story manuscript describes this lore differently from the world-building corpus.",
        "suggested_fix": f"Choose the canonical version of {world_item['name']} and update either the world document or the relevant story chapter to match it.",
        "world_evidence": _best_evidence_text(world_item),
        "story_evidence": _best_evidence_text(story_item),
    }


def _build_conflict_detail(
    name: str,
    left_item: dict,
    right_item: dict,
    left_claim: dict,
    right_claim: dict,
    *,
    source_kind: str,
) -> dict:
    left_label = _source_label(left_item, source_kind=source_kind)
    right_label = _source_label(right_item, source_kind=source_kind)
    subject = _conflict_subject(
        name, str(left_item.get("element_type") or right_item.get("element_type") or "")
    )
    description = (
        f"{subject} is described as {_claim_phrase(left_claim)} in {left_label}, "
        f"but {_claim_phrase(right_claim)} in {right_label}. No explanation found in the extracted canon."
    )
    return {
        "title": f"{name} conflicts with the {'story manuscript' if source_kind == 'cross_source' else ('manuscript itself' if source_kind == 'story' else 'world notes')}",
        "description": description,
        "suggested_fix": f"Choose whether {left_label} or {right_label} is canonical for {name}, then update the conflicting reference and add an explicit explanation if the change is intentional.",
        "world_evidence": _best_evidence_text(left_item),
        "story_evidence": _best_evidence_text(right_item),
        "world_document_id": str(left_item.get("world_document_id") or "") or None,
        "world_document_title": str(left_item.get("world_document_title") or "") or None,
        "story_chapter_number": int(right_item.get("chapter_number") or 0) or None,
        "story_chapter_title": str(right_item.get("chapter_title") or "") or None,
        "character_name": None,
        "priority": 10,
        "entity_type": str(left_item.get("element_type") or right_item.get("element_type") or ""),
        "canonical_name": name,
        "confidence": max(
            float(left_item.get("confidence") or 0.0), float(right_item.get("confidence") or 0.0)
        ),
        "provenance": {
            "world": list(left_item.get("provenance") or [])[:2],
            "story": list(right_item.get("provenance") or [])[:2],
        },
    }


def _conflict_subject(name: str, element_type: str) -> str:
    if name == "Magic System":
        return "Magic"
    if name == "Political System":
        return "Politics"
    if name == "Travel Constraints":
        return "Travel"
    if name == "Power Limits":
        return "Power use"
    return name


def _source_label(item: dict, *, source_kind: str) -> str:
    if source_kind == "story":
        chapter_number = int(item.get("chapter_number") or 0)
        return f"Chapter {chapter_number}" if chapter_number else "the manuscript"
    if source_kind == "world":
        title = str(item.get("world_document_title") or "").strip()
        return title or "the world corpus"
    if str(item.get("world_document_title") or "").strip():
        return str(item.get("world_document_title")).strip()
    chapter_number = int(item.get("chapter_number") or 0)
    return f"Chapter {chapter_number}" if chapter_number else "the story manuscript"


def _best_evidence_text(item: dict) -> str | None:
    excerpt = str(item.get("source_excerpt") or "").strip()
    if excerpt:
        return excerpt
    provenance = list(item.get("provenance") or [])
    for entry in provenance:
        excerpt = " ".join(str((entry or {}).get("excerpt") or "").split()).strip()
        if excerpt:
            return excerpt
    return " ".join(str(item.get("description") or "").split()).strip() or None


def _claim_phrase(claim: dict) -> str:
    attribute = str(claim.get("attribute") or "").strip().lower()
    value = " ".join(str(claim.get("value") or "").split()).strip()
    negated = bool(claim.get("negated"))
    if attribute == "requirement":
        return f"{'works without' if negated else 'requires'} {value}"
    if attribute == "cost":
        return f"{'happens without' if negated else 'costs'} {value}"
    if attribute == "relative_position":
        return f"is {value}"
    if attribute == "governance":
        return f"is ruled by {value}"
    if attribute == "travel_time":
        return f"takes {value}"
    if attribute == "power_limit":
        return f"{'is not limited by' if negated else 'can only'} {value}"
    if attribute == "currency":
        return f"uses {value}"
    if attribute == "legality":
        return f"{value} is {'legal' if not negated else 'illegal'}"
    if attribute == "location":
        return f"{'is not in' if negated else 'is in'} {value}"
    if attribute == "climate":
        return f"{'is not' if negated else 'is'} {value}"
    if attribute == "descriptor":
        return f"{'is not a' if negated else 'is a'} {value}"
    if attribute == "occupation":
        return f"{'is not a' if negated else 'is a'} {value}"
    return f"{'is not' if negated else 'is'} {value}"


def _claims_by_attribute(claims: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for claim in claims:
        attribute = " ".join(str(claim.get("attribute") or "").split()).strip().lower()
        value = " ".join(str(claim.get("value") or "").split()).strip()
        if not attribute or not value:
            continue
        grouped[attribute].append(
            {
                "attribute": attribute,
                "value": value,
                "confidence": float(claim.get("confidence") or 0.0),
                "negated": bool(claim.get("negated")),
                "cue": " ".join(str(claim.get("cue") or "").split()).strip() or None,
            }
        )
    return grouped


def _claims_contradict(left_claim: dict, right_claim: dict) -> bool:
    attribute = str(left_claim.get("attribute") or "")
    left_value = _normalize_text(str(left_claim.get("value") or ""))
    right_value = _normalize_text(str(right_claim.get("value") or ""))
    left_negated = bool(left_claim.get("negated"))
    right_negated = bool(right_claim.get("negated"))
    if not left_value or not right_value:
        return False
    if left_value == right_value:
        return left_negated != right_negated

    left_numbers = {token for token in left_value.split() if token.isdigit()}
    right_numbers = {token for token in right_value.split() if token.isdigit()}
    if (
        left_numbers
        and right_numbers
        and left_numbers != right_numbers
        and left_negated == right_negated
    ):
        return True

    if attribute == "relative_position":
        left_anchor = left_value.split(" of ", 1)[1] if " of " in left_value else left_value
        right_anchor = right_value.split(" of ", 1)[1] if " of " in right_value else right_value
        if (
            left_anchor == right_anchor
            and left_value != right_value
            and left_negated == right_negated
        ):
            return True

    if attribute == "travel_time" and left_value != right_value and left_negated == right_negated:
        return True

    if (
        attribute in {"requirement", "cost", "power_limit", "governance", "currency", "legality"}
        and left_value != right_value
        and left_negated == right_negated
    ):
        return True

    if attribute == "climate":
        left_bucket = _climate_bucket(left_value)
        right_bucket = _climate_bucket(right_value)
        if left_bucket and right_bucket:
            if left_bucket == right_bucket:
                return left_negated != right_negated
            if left_negated == right_negated:
                return True
            return False

    left_tokens = {token for token in left_value.split() if token not in STOPWORDS}
    right_tokens = {token for token in right_value.split() if token not in STOPWORDS}
    overlap = left_tokens & right_tokens
    if left_negated != right_negated and overlap:
        return True
    if overlap:
        if left_tokens <= right_tokens or right_tokens <= left_tokens:
            return False
        return False

    if left_negated != right_negated:
        return False
    return True


def _extract_claims_from_description(text: str) -> list[dict]:
    return extract_claims_from_text("", text, "concept")


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

    left_claims = _claims_by_attribute(_extract_claims_from_description(normalized_left))
    right_claims = _claims_by_attribute(_extract_claims_from_description(normalized_right))
    shared_attributes = set(left_claims) & set(right_claims)
    for attribute in shared_attributes:
        for left_claim in left_claims[attribute]:
            for right_claim in right_claims[attribute]:
                if _claims_contradict(left_claim, right_claim):
                    return True

    return False


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
        (
            await db.execute(
                select(WorldGapAnalysis)
                .where(
                    WorldGapAnalysis.book_id == book_id,
                    WorldGapAnalysis.series_id == series_id,
                    WorldGapAnalysis.analysis_mode == mode,
                )
                .order_by(WorldGapAnalysis.generated_at.desc())
            )
        )
        .scalars()
        .first()
    )
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


def _apply_integration_scores(
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
