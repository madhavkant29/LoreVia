"""Chapter consistency report query workflows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    Chapter,
)
from app.schemas.books import (
    ChapterConsistencyReport,
    ChapterReportCharacter,
)
from app.utils.books import (
    normalization,
)
from app.utils.books.continuity import (
    _load_chapter_consistency_context,
    parse_chapter_editorial_note,
)
from app.utils.books.imports import (
    report_sentence,
)


async def list_chapter_consistency_reports(
    db: AsyncSession,
    book: Book,
    limit: int = 12,
) -> list[ChapterConsistencyReport]:
    chapter_numbers = (
        (
            await db.execute(
                select(Chapter.number)
                .where(Chapter.book_id == book.id)
                .order_by(Chapter.number.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    context = await _load_chapter_consistency_context(db, book, chapter_numbers)

    reports: list[ChapterConsistencyReport] = []
    for chapter_number in chapter_numbers:
        chapter = context["chapters_by_number"].get(chapter_number)
        if chapter is None:
            continue
        short_summary = context["summary_by_chapter_id"].get(chapter.id)
        editorial_note = context["editorial_by_chapter_id"].get(chapter.id)
        editorial_concerns, revision_question = (
            parse_chapter_editorial_note(editorial_note.content) if editorial_note else (None, None)
        )
        new_characters = context["new_characters_by_chapter"].get(chapter_number, [])
        names_by_id = context["names_by_id"]
        relationship_changes: list[str] = []
        seen_relationships: set[tuple[str, str, str]] = set()
        for rel in context["relationships_by_chapter"].get(chapter_number, []):
            a_name = names_by_id.get(rel.character_a_id, "Unknown")
            b_name = names_by_id.get(rel.character_b_id, "Unknown")
            key = tuple(sorted((a_name, b_name)) + [rel.rel_type])
            if key in seen_relationships:
                continue
            seen_relationships.add(key)
            relationship_changes.append(
                f"{a_name} and {b_name}: {rel.rel_type.replace('_', ' ')}"
                + (f" - {rel.description}" if rel.description else "")
            )
        opened_threads = context["opened_threads_by_chapter"].get(chapter_number, [])
        resolved_threads = context["resolved_threads_by_chapter"].get(chapter_number, [])
        continuity_flags = context["continuity_flags_by_chapter"].get(chapter_number, [])
        summary_line = report_sentence(short_summary.content if short_summary else "")
        if not summary_line:
            summary_line = (
                f"{normalization.story_unit_label(book, chapter_number)} was imported and analysed."
            )
        additions = []
        if new_characters:
            additions.append(
                f"{len(new_characters)} new character{'s' if len(new_characters) != 1 else ''}"
            )
        if relationship_changes:
            additions.append(
                f"{len(relationship_changes)} relationship shift{'s' if len(relationship_changes) != 1 else ''}"
            )
        if opened_threads:
            additions.append(
                f"{len(opened_threads)} plot thread{'s' if len(opened_threads) != 1 else ''} opened"
            )
        if resolved_threads:
            additions.append(f"{len(resolved_threads)} resolved")
        if continuity_flags:
            additions.append(
                f"{len(continuity_flags)} continuity flag{'s' if len(continuity_flags) != 1 else ''}"
            )
        if additions:
            summary_line = f"{summary_line} This upload surfaced " + ", ".join(additions) + "."

        reports.append(
            ChapterConsistencyReport(
                chapter_number=chapter_number,
                chapter_title=chapter.title,
                summary=summary_line,
                new_characters=[
                    ChapterReportCharacter(
                        id=str(char.id),
                        name=char.name,
                        role=char.role,
                        first_chapter=char.first_chapter,
                        arc_summary=char.arc_summary,
                    )
                    for char in new_characters
                ],
                relationship_changes=list(dict.fromkeys(relationship_changes[:6])),
                plot_threads_opened=list(
                    dict.fromkeys(thread.title for thread in opened_threads[:6])
                ),
                plot_threads_resolved=list(
                    dict.fromkeys(thread.title for thread in resolved_threads[:6])
                ),
                continuity_flags=list(dict.fromkeys(continuity_flags[:6])),
                editorial_concerns=editorial_concerns,
                revision_question=revision_question,
            )
        )
    return reports
