from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, noload

from app.models.book import Book, BookCollaborator
from app.schemas.books import BookPageOut, BookSelectorOut
from app.utils.books import collaboration
from app.utils.books.serialization import build_book_out_list, cover_url_for_book


def encode_book_page_cursor(created_at: datetime, book_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "book_id": str(book_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_book_page_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        if created_at.tzinfo is None:
            raise ValueError("Cursor timestamp must include a timezone")
        return created_at, uuid.UUID(str(payload["book_id"]))
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
    ) as exc:
        raise HTTPException(400, "Invalid book page cursor") from exc


async def list_user_books_page(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    user_email: str,
    include_hidden: bool,
    limit: int,
    cursor: str | None,
) -> BookPageOut:
    bounded_limit = max(1, min(int(limit), 100))
    normalized_email = user_email.strip().lower()
    active_collaboration = exists(
        select(BookCollaborator.id).where(
            BookCollaborator.book_id == Book.id,
            BookCollaborator.email == normalized_email,
            BookCollaborator.invite_status == "active",
        )
    )
    statement = (
        select(Book)
        .options(noload(Book.vault_note_series_links))
        .where(or_(Book.user_id == user_id, active_collaboration))
        .order_by(Book.created_at.desc(), Book.id.desc())
        .limit(bounded_limit + 1)
    )
    if not include_hidden:
        statement = statement.where(Book.hidden_at.is_(None))
    if cursor:
        cursor_created_at, cursor_id = decode_book_page_cursor(cursor)
        statement = statement.where(
            or_(
                Book.created_at < cursor_created_at,
                and_(Book.created_at == cursor_created_at, Book.id < cursor_id),
            )
        )

    rows = list((await db.execute(statement)).scalars().all())
    has_more = len(rows) > bounded_limit
    books = rows[:bounded_limit]
    shared_ids = [book.id for book in books if book.user_id != user_id]
    collaborators_by_book_id: dict[uuid.UUID, BookCollaborator] = {}
    if shared_ids:
        collaborator_rows = list(
            (
                await db.execute(
                    select(BookCollaborator).where(
                        BookCollaborator.book_id.in_(shared_ids),
                        BookCollaborator.email == normalized_email,
                        BookCollaborator.invite_status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        collaborators_by_book_id = {row.book_id: row for row in collaborator_rows}

    items = await build_book_out_list(
        db,
        books=books,
        user_id=user_id,
        collaborators_by_book_id=collaborators_by_book_id,
    )
    next_cursor = (
        encode_book_page_cursor(books[-1].created_at, books[-1].id) if has_more and books else None
    )
    return BookPageOut(items=items, next_cursor=next_cursor)


async def list_user_book_selectors(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    user_email: str,
    include_hidden: bool,
    limit: int = 200,
) -> list[BookSelectorOut]:
    """Return navigation-sized records with one bounded book query and collaborator lookup."""
    bounded_limit = max(1, min(int(limit), 500))
    normalized_email = user_email.strip().lower()
    active_collaboration = exists(
        select(BookCollaborator.id).where(
            BookCollaborator.book_id == Book.id,
            BookCollaborator.email == normalized_email,
            BookCollaborator.invite_status == "active",
        )
    )
    statement = (
        select(Book)
        .options(
            load_only(
                Book.id,
                Book.user_id,
                Book.title,
                Book.author,
                Book.genre,
                Book.cover_s3_key,
                Book.mode,
                Book.status,
                Book.work_type,
                Book.total_chapters,
                Book.hidden_at,
                Book.archived_at,
                Book.is_public,
                Book.source_kind,
                Book.public_share_status,
                Book.public_description,
                Book.primary_series_id,
                Book.series_name,
                Book.series_order,
                Book.created_at,
            ),
            noload(Book.vault_note_series_links),
        )
        .where(or_(Book.user_id == user_id, active_collaboration))
        .order_by(Book.created_at.desc(), Book.id.desc())
        .limit(bounded_limit)
    )
    if not include_hidden:
        statement = statement.where(Book.hidden_at.is_(None))
    books = list((await db.execute(statement)).scalars().all())
    shared_ids = [book.id for book in books if book.user_id != user_id]
    collaborators_by_book_id: dict[uuid.UUID, BookCollaborator] = {}
    if shared_ids:
        collaborator_rows = list(
            (
                await db.execute(
                    select(BookCollaborator).where(
                        BookCollaborator.book_id.in_(shared_ids),
                        BookCollaborator.email == normalized_email,
                        BookCollaborator.invite_status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        collaborators_by_book_id = {row.book_id: row for row in collaborator_rows}

    items: list[BookSelectorOut] = []
    for book in books:
        collaborator = collaborators_by_book_id.get(book.id)
        access = collaboration.build_book_access_context(
            book,
            user_id=user_id,
            collaborator=collaborator,
        )
        items.append(
            BookSelectorOut(
                id=book.id,
                title=book.title,
                author=book.author,
                genre=book.genre,
                cover_url=cover_url_for_book(book),
                mode=book.mode or "reader",
                status=book.status,
                work_type=book.work_type,
                total_chapters=book.total_chapters,
                hidden_at=book.hidden_at,
                archived_at=book.archived_at,
                # Older rows can predate the database default and retain NULL.
                # The selector contract deliberately exposes a concrete boolean.
                is_public=bool(book.is_public),
                source_kind=book.source_kind,
                public_share_status=book.public_share_status,
                public_description=book.public_description,
                primary_series_id=book.primary_series_id,
                series_name=book.series_name,
                series_order=book.series_order,
                workspace_shell=access.workspace_shell,
                access_class=access.access_class,
                can_switch_workspace_mode=access.can_switch_workspace_mode,
                collaboration_role=collaborator.role if collaborator else None,
                collaboration_permissions=access.collaboration_permissions,
            )
        )
    return items
