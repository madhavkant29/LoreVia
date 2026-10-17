"""Persist accepted import outlines and expose their stable chapter metadata."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select

from app.models.book import Book, BookSection, Chapter
from app.schemas.section import SectionMeta


async def filter_analysis_eligible_chapters(db, book_id: uuid.UUID, chapters: list[Chapter]) -> list[Chapter]:
    """Retain legacy chapters and omit sections explicitly excluded at import."""
    excluded_ids = set((await db.execute(
        select(BookSection.chapter_id).where(
            BookSection.book_id == book_id,
            BookSection.include_in_analysis.is_(False),
            BookSection.chapter_id.is_not(None),
        )
    )).scalars().all())
    return [chapter for chapter in chapters if chapter.id not in excluded_ids]


async def persist_book_sections(
    db,
    *,
    book: Book,
    plan: dict[str, Any],
    chapter_rows: list[Chapter],
    chapters: list[dict[str, Any]],
    import_scope: str | None = None,
) -> None:
    """Write the new import only; leave preexisting chapter rows unchanged."""
    chapter_by_number = {chapter.number: chapter for chapter in chapter_rows}
    chapter_by_section = {
        data.get("structure_section_id"): chapter_by_number.get(data["number"])
        for data in chapters if data.get("structure_section_id")
    }
    existing = {
        row for row in (await db.execute(
            select(BookSection.id).where(BookSection.book_id == book.id)
        )).scalars().all()
    }
    scope = import_scope or str(book.id)
    max_order = await db.scalar(
        select(func.max(BookSection.display_order)).where(BookSection.book_id == book.id)
    )
    offset = int(max_order) + 1 if max_order is not None else 0
    for order, raw in enumerate(plan.get("sections") or []):
        section = SectionMeta.model_validate(raw)
        row_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{scope}:{section.id}")
        if row_id in existing:
            continue
        chapter = chapter_by_section.get(section.id)
        db.add(BookSection(
            id=row_id,
            book_id=book.id,
            parent_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{scope}:{section.parent_id}")
            if section.parent_id else None,
            chapter_id=chapter.id if chapter else None,
            source_section_id=section.id,
            kind=section.type,
            title=section.title,
            source_label=section.source_label,
            source_location=section.source_location,
            display_order=offset + order,
            start_block=section.start_block,
            end_block=section.end_block,
            include_in_analysis=section.include_in_analysis,
            warnings=section.warnings,
        ))
        await db.flush()


def append_import_structure_plans(book: Book, batches: list[dict[str, Any]]) -> None:
    """Keep accepted later imports without replacing the original book outline."""
    if not batches:
        return
    existing = dict(book.import_structure or {})
    additional = list(existing.get("additional_imports") or [])
    scopes = {str(item.get("scope")) for item in additional}
    for batch in batches:
        scope = str(batch["scope"])
        if scope not in scopes:
            additional.append({"scope": scope, "plan": batch["plan"]})
            scopes.add(scope)
    existing["additional_imports"] = additional
    book.import_structure = existing
