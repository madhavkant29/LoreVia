from __future__ import annotations

import re

from app.models.intelligence import WorldBuildingDocument, WorldElement

WORLD_QUERY_STOPWORDS = {
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


def serialize_world_document(document: WorldBuildingDocument) -> dict:
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


def serialize_world_element(element: WorldElement) -> dict:
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


def map_element_to_wiki_type(element_type: str) -> str:
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


def rank_world_elements_for_query(elements: list[WorldElement], query: str) -> list[WorldElement]:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9']+", (query or "").lower())
        if token not in WORLD_QUERY_STOPWORDS
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


def count_words(text: str) -> int:
    cleaned = " ".join((text or "").split()).strip()
    return len(cleaned.split()) if cleaned else 0


def filename_title(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in cleaned.split()) or "Worldbuilding Manuscript"
