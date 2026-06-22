"""
Book utility helpers ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import bleach  # type: ignore[import-untyped]
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    BookCollaborator,
    BookNote,
    Chapter,
    ManuscriptAnnotation,
    Series,
)
from app.models.user import User
from app.utils.books import collaboration_access
from app.utils.tag_utils import (
    ENTITY_TYPE_NOTE,
    get_custom_tags_for_entity,
    list_custom_tags_for_entity_ids,
)

if TYPE_CHECKING:
    pass

BLEACH_EMPTY_TAGS: Any = frozenset()
MANUSCRIPT_ANNOTATION_STATUSES = {"open", "resolved"}
MANUSCRIPT_ANNOTATION_VISIBILITIES = {"shared", "private"}
MANUSCRIPT_ANNOTATION_CATEGORIES = {
    "general",
    "continuity",
    "character",
    "worldbuilding",
    "pacing",
    "line_edit",
    "theme",
}


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


def _clean_optional_text(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None


async def get_owned_book(
    db: AsyncSession,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    options: tuple | None = None,
) -> Book:
    if options:
        result = await db.execute(
            select(Book).where(Book.id == book_id, Book.user_id == user_id).options(*options)
        )
        book = result.scalars().first()
    else:
        book = await db.get(Book, book_id)
    if not book or book.user_id != user_id:
        raise HTTPException(404, "Book not found")
    return book


async def get_owned_series(db: AsyncSession, series_id: uuid.UUID, user_id: uuid.UUID) -> Series:
    series = await db.get(Series, series_id)
    if not series or series.user_id != user_id:
        raise HTTPException(404, "Series not found")
    return series


async def list_book_notes(
    db: AsyncSession,
    book: Book,
    *,
    collaborator: BookCollaborator | None = None,
) -> list[dict]:
    rows = list(
        (
            await db.execute(
                select(BookNote, Chapter.title)
                .outerjoin(
                    Chapter,
                    (Chapter.book_id == BookNote.book_id)
                    & (Chapter.number == BookNote.chapter_number),
                )
                .where(BookNote.book_id == book.id)
                .order_by(BookNote.chapter_number.asc().nullsfirst(), BookNote.updated_at.desc())
            )
        ).all()
    )
    tags_by_note = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_NOTE,
        entity_ids=[note.id for note, _chapter_title in rows],
        book_id=book.id,
    )
    notes = [
        {
            "id": str(note.id),
            "book_id": str(book.id),
            "book_title": book.title,
            "chapter_number": note.chapter_number,
            "chapter_title": chapter_title,
            "title": note.title,
            "body": note.body,
            "tags": tags_by_note.get(note.id, []),
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note, chapter_title in rows
    ]
    if collaborator is None:
        return notes
    return [
        note
        for note in notes
        if note["chapter_number"] is None
        or collaboration_access.collaboration_allows_chapter(
            collaborator, int(note["chapter_number"])
        )
    ]


async def list_user_notes(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = list(
        (
            await db.execute(
                select(BookNote, Book.title, Chapter.title)
                .join(Book, Book.id == BookNote.book_id)
                .outerjoin(
                    Chapter,
                    (Chapter.book_id == BookNote.book_id)
                    & (Chapter.number == BookNote.chapter_number),
                )
                .where(BookNote.user_id == user_id)
                .order_by(BookNote.updated_at.desc())
            )
        ).all()
    )
    tags_by_note = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_NOTE,
        entity_ids=[note.id for note, _book_title, _chapter_title in rows],
    )
    return [
        {
            "id": str(note.id),
            "book_id": str(note.book_id),
            "book_title": book_title,
            "chapter_number": note.chapter_number,
            "chapter_title": chapter_title,
            "title": note.title,
            "body": note.body,
            "tags": tags_by_note.get(note.id, []),
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note, book_title, chapter_title in rows
    ]


def _annotation_category(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if not normalized:
        return "general"
    if normalized not in MANUSCRIPT_ANNOTATION_CATEGORIES:
        raise HTTPException(400, "Invalid annotation category")
    return normalized


def _annotation_status(value: str | None) -> str:
    normalized = str(value or "open").strip().lower()
    if normalized not in MANUSCRIPT_ANNOTATION_STATUSES:
        raise HTTPException(400, "Invalid annotation status")
    return normalized


def _annotation_visibility(value: str | None) -> str:
    normalized = str(value or "shared").strip().lower()
    if normalized not in MANUSCRIPT_ANNOTATION_VISIBILITIES:
        raise HTTPException(400, "Invalid annotation visibility")
    return normalized


def _annotation_actor_label(user: User) -> str:
    username = " ".join(str(user.username or "").split()).strip()
    if username:
        return username
    email_name = str(user.email or "").split("@", 1)[0].strip()
    return email_name or "Reviewer"


def _can_edit_annotation(
    annotation: ManuscriptAnnotation, *, actor_user_id: uuid.UUID, book_owner_id: uuid.UUID
) -> bool:
    return annotation.user_id == actor_user_id or book_owner_id == actor_user_id


def _serialize_manuscript_annotation(
    annotation: ManuscriptAnnotation,
    *,
    book: Book,
    chapter_title: str | None,
    actor_user_id: uuid.UUID,
    created_by_label: str,
) -> dict[str, Any]:
    return {
        "id": str(annotation.id),
        "book_id": str(book.id),
        "book_title": book.title,
        "chapter_number": annotation.chapter_number,
        "chapter_title": chapter_title,
        "category": annotation.category,
        "status": annotation.status,
        "visibility": annotation.visibility,
        "quote": annotation.quote,
        "comment": annotation.comment,
        "anchor_context_before": annotation.anchor_context_before,
        "anchor_context_after": annotation.anchor_context_after,
        "start_offset": annotation.start_offset,
        "end_offset": annotation.end_offset,
        "created_by_user_id": str(annotation.user_id),
        "created_by_label": created_by_label,
        "can_edit": _can_edit_annotation(
            annotation, actor_user_id=actor_user_id, book_owner_id=book.user_id
        ),
        "resolved_at": annotation.resolved_at,
        "created_at": annotation.created_at,
        "updated_at": annotation.updated_at,
    }


async def list_manuscript_annotations(
    db: AsyncSession,
    *,
    book: Book,
    actor: User,
    collaborator: BookCollaborator | None = None,
    chapter_number: int | None = None,
) -> list[dict[str, Any]]:
    query = (
        select(ManuscriptAnnotation, Chapter.title, User.username, User.email)
        .join(User, User.id == ManuscriptAnnotation.user_id)
        .outerjoin(
            Chapter,
            (Chapter.book_id == ManuscriptAnnotation.book_id)
            & (Chapter.number == ManuscriptAnnotation.chapter_number),
        )
        .where(ManuscriptAnnotation.book_id == book.id)
        .order_by(
            ManuscriptAnnotation.chapter_number.asc(),
            ManuscriptAnnotation.status.asc(),
            ManuscriptAnnotation.updated_at.desc(),
        )
    )
    if chapter_number is not None:
        query = query.where(ManuscriptAnnotation.chapter_number == chapter_number)

    rows = (await db.execute(query)).all()
    payload: list[dict[str, Any]] = []
    for annotation, chapter_title, username, email in rows:
        if collaborator is not None and not collaboration_access.collaboration_allows_chapter(
            collaborator, annotation.chapter_number
        ):
            continue
        if annotation.visibility == "private" and annotation.user_id != actor.id:
            continue
        payload.append(
            _serialize_manuscript_annotation(
                annotation,
                book=book,
                chapter_title=chapter_title,
                actor_user_id=actor.id,
                created_by_label=" ".join(str(username or "").split()).strip()
                or str(email or "").split("@", 1)[0]
                or "Reviewer",
            )
        )
    return payload


async def save_manuscript_annotation(
    db: AsyncSession,
    *,
    book: Book,
    actor: User,
    annotation_id: str | None,
    chapter_number: int | None,
    category: str | None,
    status: str | None,
    visibility: str | None,
    quote: str | None,
    comment: str | None,
    anchor_context_before: str | None,
    anchor_context_after: str | None,
    start_offset: int | None,
    end_offset: int | None,
) -> dict[str, Any]:
    annotation: ManuscriptAnnotation | None = None
    if annotation_id:
        try:
            parsed_annotation_id = uuid.UUID(annotation_id)
        except ValueError as exc:
            raise HTTPException(400, "Invalid annotation id") from exc
        annotation = await db.get(ManuscriptAnnotation, parsed_annotation_id)
        if not annotation or annotation.book_id != book.id:
            raise HTTPException(404, "Annotation not found")
        if not _can_edit_annotation(annotation, actor_user_id=actor.id, book_owner_id=book.user_id):
            raise HTTPException(403, "You cannot edit this annotation.")
    else:
        annotation = ManuscriptAnnotation(
            user_id=actor.id,
            book_id=book.id,
        )
        db.add(annotation)

    normalized_chapter_number = (
        chapter_number if chapter_number is not None else annotation.chapter_number
    )
    if normalized_chapter_number is None or normalized_chapter_number < 1:
        raise HTTPException(400, "Annotation chapter is required")

    normalized_quote = _clean_text(quote if quote is not None else annotation.quote)
    normalized_comment = _clean_text(comment if comment is not None else annotation.comment)
    if not normalized_quote:
        raise HTTPException(400, "Annotation quote is required")
    if not normalized_comment:
        raise HTTPException(400, "Annotation comment is required")

    normalized_start_offset = start_offset if start_offset is not None else annotation.start_offset
    normalized_end_offset = end_offset if end_offset is not None else annotation.end_offset
    if (
        normalized_start_offset is not None
        and normalized_end_offset is not None
        and normalized_end_offset < normalized_start_offset
    ):
        raise HTTPException(400, "Annotation offsets are invalid")

    annotation.chapter_number = normalized_chapter_number
    annotation.category = _annotation_category(
        category if category is not None else annotation.category
    )
    annotation.status = _annotation_status(status if status is not None else annotation.status)
    annotation.visibility = _annotation_visibility(
        visibility if visibility is not None else annotation.visibility
    )
    annotation.quote = normalized_quote
    annotation.comment = normalized_comment
    annotation.anchor_context_before = _clean_optional_text(
        anchor_context_before
        if anchor_context_before is not None
        else annotation.anchor_context_before
    )
    annotation.anchor_context_after = _clean_optional_text(
        anchor_context_after
        if anchor_context_after is not None
        else annotation.anchor_context_after
    )
    annotation.start_offset = normalized_start_offset
    annotation.end_offset = normalized_end_offset
    annotation.resolved_at = datetime.now(UTC) if annotation.status == "resolved" else None

    await db.commit()
    await db.refresh(annotation)

    chapter_title = (
        await db.execute(
            select(Chapter.title).where(
                Chapter.book_id == book.id, Chapter.number == annotation.chapter_number
            )
        )
    ).scalar_one_or_none()
    creator = actor if annotation.user_id == actor.id else await db.get(User, annotation.user_id)
    return _serialize_manuscript_annotation(
        annotation,
        book=book,
        chapter_title=chapter_title,
        actor_user_id=actor.id,
        created_by_label=_annotation_actor_label(creator or actor),
    )


async def delete_manuscript_annotation(
    db: AsyncSession,
    *,
    book: Book,
    actor: User,
    annotation_id: uuid.UUID,
) -> None:
    annotation = await db.get(ManuscriptAnnotation, annotation_id)
    if not annotation or annotation.book_id != book.id:
        raise HTTPException(404, "Annotation not found")
    if not _can_edit_annotation(annotation, actor_user_id=actor.id, book_owner_id=book.user_id):
        raise HTTPException(403, "You cannot delete this annotation.")
    await db.delete(annotation)
    await db.commit()


async def save_book_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    note_id: str | None,
    chapter_number: int | None,
    title: str | None,
    body: str,
) -> dict:
    normalized_title = _clean_optional_text(" ".join((title or "").split()).strip())
    normalized_body = _clean_text(body)
    if not normalized_body:
        raise HTTPException(400, "Note body is required")

    if chapter_number is not None and chapter_number < 1:
        raise HTTPException(400, "Invalid chapter number")

    note: BookNote | None = None
    if note_id:
        try:
            parsed_note_id = uuid.UUID(note_id)
        except ValueError as exc:
            raise HTTPException(400, "Invalid note id") from exc
        note = await db.get(BookNote, parsed_note_id)
        if not note or note.user_id != user_id or note.book_id != book.id:
            raise HTTPException(404, "Note not found")
    else:
        note = BookNote(user_id=user_id, book_id=book.id)
        db.add(note)

    note_any = cast(Any, note)
    note_any.chapter_number = chapter_number
    note_any.title = normalized_title
    note_any.body = normalized_body
    await db.commit()
    await db.refresh(note)

    chapter_title = None
    if note.chapter_number is not None:
        chapter_title = (
            await db.execute(
                select(Chapter.title).where(
                    Chapter.book_id == book.id, Chapter.number == note.chapter_number
                )
            )
        ).scalar_one_or_none()

    return {
        "id": str(note.id),
        "book_id": str(book.id),
        "book_title": book.title,
        "chapter_number": note.chapter_number,
        "chapter_title": chapter_title,
        "title": note.title,
        "body": note.body,
        "tags": await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_NOTE,
            entity_id=note.id,
            book_id=book.id,
        ),
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def delete_book_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    note_id: uuid.UUID,
) -> None:
    deleted = await db.execute(
        delete(BookNote).where(
            BookNote.id == note_id,
            BookNote.user_id == user_id,
            BookNote.book_id == book.id,
        )
    )
    if not deleted.rowcount:
        raise HTTPException(404, "Note not found")
    await db.commit()


async def resolve_owned_series_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
    series_ids: list[str],
) -> list[Series]:
    cleaned_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    for raw in series_ids:
        value = (raw or "").strip()
        if not value:
            continue
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise HTTPException(400, "Invalid series id") from exc
        if parsed in seen:
            continue
        seen.add(parsed)
        cleaned_ids.append(parsed)

    if not cleaned_ids:
        return []

    rows = (
        (
            await db.execute(
                select(Series).where(Series.user_id == user_id, Series.id.in_(cleaned_ids))
            )
        )
        .scalars()
        .all()
    )
    found = {series.id for series in rows}
    if len(found) != len(cleaned_ids):
        raise HTTPException(404, "Series not found")

    order = {series_id: index for index, series_id in enumerate(cleaned_ids)}
    return sorted(rows, key=lambda series: order[series.id])
