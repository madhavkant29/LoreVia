from __future__ import annotations

import asyncio
import json
import uuid
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.core.security import hash_password
from app.models.beta_read import BetaReadAssignment, BetaReadFeedbackItem, BetaReadQuestion
from app.models.book import (
    Book,
    BookCollaborator,
    BookForumComment,
    BookForumInterest,
    BookForumPost,
    BookNote,
    Chapter,
    ChapterMedia,
    ChapterVersion,
    ManuscriptAnnotation,
    SceneVersion,
)
from app.models.character import Character
from app.models.intelligence import (
    AdvisorJob,
    CharacterRelationship,
    Notification,
    PlotThread,
    WikiEntry,
    WorldBuildingDocument,
    WorldElement,
    WorldNote,
)
from app.models.progress import ReadingProgress, ReadingSession
from app.models.social import DirectConversation, DirectMessage, FriendRequest
from app.models.user import (
    DataDeletionRequest,
    DeviceTrial,
    EmailPreference,
    LlmUsageEvent,
    Subscription,
    TrialEmailEvent,
    User,
    UserLoginActivity,
    UserWritingActivity,
)
from app.services.paddle_service import cancel_subscription_at_period_end
from app.services.supabase_auth_service import delete_supabase_auth_user
from app.utils.auth_utils import next_token_version, verify_password_safely
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
)
from app.utils.privacy_utils import (
    DATA_DELETION_STATUS_COMPLETED,
    DATA_DELETION_STATUS_FAILED,
    DATA_DELETION_STATUS_PENDING,
    DATA_DELETION_STATUS_PROCESSING,
    USER_DELETION_STATUS_ACTIVE,
    USER_DELETION_STATUS_DELETED,
    USER_DELETION_STATUS_PENDING,
    USER_DELETION_STATUS_PROVIDER_FOLLOWUP,
    data_deletion_scheduled_for,
    deleted_account_email,
    hash_deleted_email,
    user_is_deleted,
    validate_account_deletion_confirmation,
    validate_book_deletion_confirmation,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS

PADDLE_PROVIDER_EXCEPTIONS = (httpx.HTTPError, KeyError, TypeError, ValueError)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, uuid.UUID)):
        return str(value)
    return str(value)


def _model_payload(model: Any, fields: list[str]) -> dict[str, Any]:
    return {field: getattr(model, field, None) for field in fields}


def _write_json(zip_file: zipfile.ZipFile, path: str, payload: Any) -> None:
    zip_file.writestr(path, json.dumps(payload, default=_json_default, indent=2, sort_keys=True))


async def _download_text_or_error(key: str) -> dict[str, Any]:
    try:
        raw = await asyncio.to_thread(storage.download_book, key)
        try:
            content = deserialize_manuscript_content(raw)
            return {
                "storage_key": key,
                "text": content.text,
                "html": content.html,
                "metadata": content.metadata,
            }
        except (AttributeError, TypeError, ValueError):
            return {"storage_key": key, "text": raw.decode("utf-8", errors="replace")}
    except STORAGE_IO_EXCEPTIONS as exc:
        return {"storage_key": key, "error": str(exc)}


async def build_user_data_export(db: AsyncSession, user: User) -> bytes:
    books = (
        (
            await db.execute(
                select(Book).where(Book.user_id == user.id).order_by(Book.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    email_preferences = (
        await db.execute(select(EmailPreference).where(EmailPreference.user_id == user.id))
    ).scalar_one_or_none()

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        _write_json(
            zip_file,
            "account.json",
            {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "tier": user.tier,
                "reading_mode": user.reading_mode,
                "daily_word_goal": user.daily_word_goal,
                "legal_version": user.legal_version,
                "legal_accepted_at": user.legal_accepted_at,
                "created_at": user.created_at,
            },
        )
        _write_json(
            zip_file,
            "email_preferences.json",
            _model_payload(
                email_preferences,
                ["marketing_enabled", "product_enabled", "beta_reader_enabled", "updated_at"],
            )
            if email_preferences
            else {},
        )
        _write_json(
            zip_file,
            "books/index.json",
            [
                _model_payload(
                    book,
                    [
                        "id",
                        "title",
                        "author",
                        "genre",
                        "format",
                        "work_type",
                        "status",
                        "mode",
                        "is_public",
                        "public_status",
                        "created_at",
                        "archived_at",
                        "hidden_at",
                    ],
                )
                for book in books
            ],
        )

        for book in books:
            prefix = f"books/{book.id}"
            _write_json(
                zip_file,
                f"{prefix}/book.json",
                _model_payload(
                    book,
                    [
                        "id",
                        "title",
                        "author",
                        "genre",
                        "format",
                        "work_type",
                        "status",
                        "source_kind",
                        "total_chapters",
                        "total_tokens",
                        "total_words",
                        "is_public",
                        "public_description",
                        "public_status",
                        "created_at",
                    ],
                ),
            )
            chapters = (
                (
                    await db.execute(
                        select(Chapter)
                        .where(Chapter.book_id == book.id)
                        .order_by(Chapter.number.asc())
                    )
                )
                .scalars()
                .all()
            )
            _write_json(
                zip_file,
                f"{prefix}/chapters.json",
                [
                    {
                        **_model_payload(
                            chapter,
                            [
                                "id",
                                "number",
                                "title",
                                "description",
                                "chapter_kind",
                                "word_count",
                                "token_count",
                            ],
                        ),
                        "manuscript": await _download_text_or_error(chapter.s3_key),
                    }
                    for chapter in chapters
                ],
            )
            for filename, model, fields in (
                (
                    "notes.json",
                    BookNote,
                    ["id", "chapter_number", "title", "body", "created_at", "updated_at"],
                ),
                (
                    "annotations.json",
                    ManuscriptAnnotation,
                    [
                        "id",
                        "chapter_number",
                        "category",
                        "status",
                        "visibility",
                        "quote",
                        "comment",
                        "created_at",
                    ],
                ),
                (
                    "characters.json",
                    Character,
                    [
                        "id",
                        "name",
                        "display_name",
                        "status",
                        "description",
                        "mention_count",
                        "created_at",
                    ],
                ),
                (
                    "relationships.json",
                    CharacterRelationship,
                    [
                        "id",
                        "character_a_id",
                        "character_b_id",
                        "relationship_type",
                        "description",
                        "confidence",
                    ],
                ),
                (
                    "plot_threads.json",
                    PlotThread,
                    ["id", "title", "status", "description", "created_at", "updated_at"],
                ),
                (
                    "wiki_entries.json",
                    WikiEntry,
                    ["id", "title", "entry_type", "body", "created_at", "updated_at"],
                ),
                (
                    "world_elements.json",
                    WorldElement,
                    [
                        "id",
                        "element_type",
                        "name",
                        "description",
                        "usage_count",
                        "created_at",
                        "updated_at",
                    ],
                ),
                (
                    "world_notes.json",
                    WorldNote,
                    ["id", "title", "body", "created_at", "updated_at"],
                ),
                (
                    "beta_read_assignments.json",
                    BetaReadAssignment,
                    [
                        "id",
                        "author_user_id",
                        "reader_user_id",
                        "reader_email",
                        "state",
                        "scope_kind",
                        "task_label",
                        "created_at",
                        "updated_at",
                    ],
                ),
                (
                    "collaborators.json",
                    BookCollaborator,
                    [
                        "id",
                        "invited_user_id",
                        "email",
                        "display_name",
                        "role",
                        "scope",
                        "permissions",
                        "invite_status",
                        "invited_at",
                        "updated_at",
                    ],
                ),
            ):
                rows = (
                    (await db.execute(select(model).where(model.book_id == book.id)))
                    .scalars()
                    .all()
                )
                _write_json(
                    zip_file, f"{prefix}/{filename}", [_model_payload(row, fields) for row in rows]
                )

    return buffer.getvalue()


async def collect_book_storage_keys(db: AsyncSession, book_id: uuid.UUID) -> list[str]:
    keys: list[str] = []

    def add(value: str | None) -> None:
        if value and value not in keys:
            keys.append(value)

    book = await db.get(Book, book_id)
    if book:
        add(book.s3_key)
        add(book.cover_s3_key)
    for model, column in (
        (Chapter, Chapter.s3_key),
        (ChapterVersion, ChapterVersion.s3_key),
        (SceneVersion, SceneVersion.s3_key),
        (WorldBuildingDocument, WorldBuildingDocument.s3_key),
        (ChapterMedia, ChapterMedia.storage_key),
        (BookForumPost, BookForumPost.image_s3_key),
        (BookForumComment, BookForumComment.image_s3_key),
    ):
        rows = (
            (await db.execute(select(column).where(model.book_id == book_id, column.is_not(None))))
            .scalars()
            .all()
        )
        for key in rows:
            add(key)
    return keys


async def queue_book_permanent_deletion(
    db: AsyncSession, book: Book, confirmation_text: str, requested_by: User
) -> DataDeletionRequest:
    try:
        validate_book_deletion_confirmation(confirmation_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    now = datetime.now(UTC)
    keys = await collect_book_storage_keys(db, book.id)
    book.hidden_at = now
    book.archived_at = None
    book.is_public = False
    book.public_status = "removed"
    book.public_visibility = "private"
    book.public_share_status = "removed"
    request = DataDeletionRequest(
        user_id=requested_by.id,
        book_id=book.id,
        request_type="book",
        status=DATA_DELETION_STATUS_PENDING,
        scheduled_for=now,
        storage_keys_json=keys,
        metadata_json={"title": book.title, "requested_by_user_id": str(requested_by.id)},
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


async def request_account_deletion(
    db: AsyncSession,
    user: User,
    *,
    confirmation_text: str,
    password: str | None,
) -> tuple[DataDeletionRequest, bool]:
    try:
        validate_account_deletion_confirmation(confirmation_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if user_is_deleted(user):
        raise HTTPException(409, "Account deletion is already in progress.")
    if user.supabase_auth_id is None:
        if not password:
            raise HTTPException(400, "Current password is required to delete this account.")
        password_ok = verify_password_safely(password, user.password_hash)
        if not password_ok:
            raise HTTPException(403, "Current password is incorrect.")

    now = datetime.now(UTC)
    scheduled_for = data_deletion_scheduled_for(now, days=settings.DATA_DELETION_GRACE_DAYS)
    provider_actions: dict[str, Any] = {"paddle": [], "supabase": None}
    followup_required = False

    subscriptions = (
        (
            await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.paddle_sub_id.is_not(None),
                    Subscription.status.in_(["active", "trialing", "past_due"]),
                )
            )
        )
        .scalars()
        .all()
    )
    for subscription in subscriptions:
        try:
            provider_response = await cancel_subscription_at_period_end(
                str(subscription.paddle_sub_id)
            )
            provider_actions["paddle"].append(
                {
                    "subscription_id": subscription.paddle_sub_id,
                    "status": "cancelled_at_period_end",
                    "response": provider_response,
                }
            )
            subscription.status = "cancelling"
        except PADDLE_PROVIDER_EXCEPTIONS as exc:
            followup_required = True
            provider_actions["paddle"].append(
                {
                    "subscription_id": subscription.paddle_sub_id,
                    "status": "followup_required",
                    "error": str(exc),
                }
            )

    original_email = user.email
    supabase_result = await delete_supabase_auth_user(user.supabase_auth_id)
    provider_actions["supabase"] = supabase_result
    if supabase_result.get("followup_required"):
        followup_required = True
    elif supabase_result.get("deleted"):
        user.supabase_auth_id = None

    books = (await db.execute(select(Book).where(Book.user_id == user.id))).scalars().all()
    storage_keys: list[str] = []
    for book in books:
        book.hidden_at = now
        book.archived_at = None
        book.is_public = False
        book.public_status = "removed"
        book.public_visibility = "private"
        book.public_share_status = "removed"
        for key in await collect_book_storage_keys(db, book.id):
            if key not in storage_keys:
                storage_keys.append(key)
    forum_image_keys = (
        (
            await db.execute(
                select(BookForumPost.image_s3_key).where(
                    BookForumPost.author_user_id == user.id,
                    BookForumPost.image_s3_key.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    forum_comment_image_keys = (
        (
            await db.execute(
                select(BookForumComment.image_s3_key).where(
                    BookForumComment.author_user_id == user.id,
                    BookForumComment.image_s3_key.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for key in [*forum_image_keys, *forum_comment_image_keys]:
        if key and key not in storage_keys:
            storage_keys.append(key)

    user.deleted_email_hash = hash_deleted_email(original_email)
    user.email = deleted_account_email(user.id)
    user.username = None
    user.password_hash = hash_password(uuid.uuid4().hex + uuid.uuid4().hex)
    user.tier = "free"
    user.token_version = next_token_version(user)
    user.deletion_status = (
        USER_DELETION_STATUS_PROVIDER_FOLLOWUP
        if followup_required
        else USER_DELETION_STATUS_PENDING
    )
    user.deletion_requested_at = now
    user.deletion_scheduled_for = scheduled_for
    user.deleted_at = now
    user.deletion_provider_status = "followup_required" if followup_required else "submitted"
    user.deletion_provider_metadata_json = provider_actions

    request = DataDeletionRequest(
        user_id=user.id,
        request_type="account",
        status=DATA_DELETION_STATUS_PENDING,
        scheduled_for=scheduled_for,
        storage_keys_json=storage_keys,
        provider_actions_json=provider_actions,
        metadata_json={"original_email_hash": user.deleted_email_hash},
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request, followup_required


async def delete_storage_keys(keys: list[str]) -> dict[str, Any]:
    deleted: list[str] = []
    errors: dict[str, str] = {}
    for key in dict.fromkeys([key for key in keys if key]):
        try:
            await asyncio.to_thread(storage.delete_object, key)
            deleted.append(key)
        except STORAGE_IO_EXCEPTIONS as exc:
            errors[key] = str(exc)
    return {"deleted": deleted, "errors": errors}


async def _hard_delete_book(db: AsyncSession, book_id: uuid.UUID | None) -> None:
    if not book_id:
        return
    book = await db.get(Book, book_id)
    if book:
        await db.delete(book)


async def _hard_delete_account_product_data(db: AsyncSession, request: DataDeletionRequest) -> None:
    user_id = request.user_id
    if not user_id:
        return

    book_ids = list(
        (await db.execute(select(Book.id).where(Book.user_id == user_id))).scalars().all()
    )
    for book_id in book_ids:
        await _hard_delete_book(db, book_id)

    for model in (
        Notification,
        DeviceTrial,
        TrialEmailEvent,
        UserWritingActivity,
        LlmUsageEvent,
        UserLoginActivity,
        EmailPreference,
        ReadingProgress,
        ReadingSession,
    ):
        if hasattr(model, "user_id"):
            await db.execute(delete(model).where(model.user_id == user_id))

    await db.execute(
        delete(BetaReadFeedbackItem).where(
            or_(
                BetaReadFeedbackItem.author_user_id == user_id,
                BetaReadFeedbackItem.reader_user_id == user_id,
            )
        )
    )
    await db.execute(delete(BetaReadQuestion).where(BetaReadQuestion.author_user_id == user_id))
    await db.execute(
        delete(BetaReadAssignment).where(
            or_(
                BetaReadAssignment.author_user_id == user_id,
                BetaReadAssignment.reader_user_id == user_id,
            )
        )
    )
    await db.execute(delete(BookCollaborator).where(BookCollaborator.invited_user_id == user_id))
    await db.execute(
        delete(BookForumInterest).where(
            or_(
                BookForumInterest.author_user_id == user_id,
                BookForumInterest.interested_user_id == user_id,
            )
        )
    )
    await db.execute(delete(BookForumPost).where(BookForumPost.author_user_id == user_id))
    await db.execute(delete(BookForumComment).where(BookForumComment.author_user_id == user_id))
    await db.execute(delete(DirectMessage).where(DirectMessage.sender_user_id == user_id))
    await db.execute(
        delete(DirectConversation).where(
            or_(
                DirectConversation.participant_a_user_id == user_id,
                DirectConversation.participant_b_user_id == user_id,
            )
        )
    )
    await db.execute(
        delete(FriendRequest).where(
            or_(
                FriendRequest.requester_user_id == user_id,
                FriendRequest.addressee_user_id == user_id,
            )
        )
    )
    await db.execute(delete(AdvisorJob).where(AdvisorJob.user_id == user_id))

    user = await db.get(User, user_id)
    if user:
        user.deletion_status = USER_DELETION_STATUS_DELETED
        user.deletion_provider_status = user.deletion_provider_status or "completed"
        user.email = deleted_account_email(user.id)
        user.username = None
        user.tier = "free"
        user.supabase_auth_id = None
        user.deletion_scheduled_for = None
        user.deleted_at = user.deleted_at or datetime.now(UTC)


async def process_data_deletion_request(
    db: AsyncSession, request: DataDeletionRequest
) -> dict[str, Any]:
    if request.status == DATA_DELETION_STATUS_COMPLETED:
        return {"id": str(request.id), "status": request.status, "skipped": True}

    now = datetime.now(UTC)
    request.status = DATA_DELETION_STATUS_PROCESSING
    request.started_at = request.started_at or now
    request.attempts = int(request.attempts or 0) + 1
    await db.flush()

    storage_result = await delete_storage_keys(list(request.storage_keys_json or []))
    if storage_result["errors"]:
        request.status = DATA_DELETION_STATUS_FAILED
        request.error_detail = json.dumps(storage_result["errors"], sort_keys=True)
        await db.flush()
        return {"id": str(request.id), "status": request.status, "storage": storage_result}

    if request.request_type == "book":
        await _hard_delete_book(db, request.book_id)
    elif request.request_type == "account":
        await _hard_delete_account_product_data(db, request)
    else:
        request.status = DATA_DELETION_STATUS_FAILED
        request.error_detail = f"Unknown deletion request type: {request.request_type}"
        await db.flush()
        return {"id": str(request.id), "status": request.status}

    request.status = DATA_DELETION_STATUS_COMPLETED
    request.completed_at = now
    request.error_detail = None
    await db.flush()
    return {"id": str(request.id), "status": request.status, "storage": storage_result}


async def process_due_data_deletion_requests(
    db: AsyncSession, *, limit: int = 50
) -> dict[str, Any]:
    now = datetime.now(UTC)
    requests = (
        (
            await db.execute(
                select(DataDeletionRequest)
                .where(
                    DataDeletionRequest.status.in_(
                        [DATA_DELETION_STATUS_PENDING, DATA_DELETION_STATUS_FAILED]
                    ),
                    DataDeletionRequest.scheduled_for <= now,
                )
                .order_by(
                    DataDeletionRequest.scheduled_for.asc(), DataDeletionRequest.requested_at.asc()
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    results = []
    for request in requests:
        results.append(await process_data_deletion_request(db, request))
        await db.commit()
    return {"processed": len(results), "results": results}


async def book_or_owner_deleted(db: AsyncSession, book_id: uuid.UUID) -> bool:
    row = (
        await db.execute(
            select(Book.hidden_at, User.deletion_status, User.deleted_at)
            .join(User, User.id == Book.user_id)
            .where(Book.id == book_id)
        )
    ).first()
    if not row:
        return True
    _, deletion_status, deleted_at = row
    return (
        deletion_status or USER_DELETION_STATUS_ACTIVE
    ) != USER_DELETION_STATUS_ACTIVE or deleted_at is not None
