from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_asset_token, decode_token
from app.core.storage import download_book, get_presigned_url, upload_binary
from app.models.book import (
    BookForumComment,
    BookForumPost,
)
from app.schemas.public import (
    PublicForumCommentCreateBody,
    PublicForumPostCreateBody,
    PublicForumPostUpdateBody,
)
from app.utils.client_identity import trusted_client_ip
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS

FORUM_POST_OPEN = "open"
FORUM_POST_CLOSED = "closed"
VALID_FORUM_POST_STATUSES = {FORUM_POST_OPEN, FORUM_POST_CLOSED}
FORUM_THREAD_TYPE_NOVEL = "novel"
FORUM_THREAD_TYPE_GENERAL = "general"
VALID_FORUM_THREAD_TYPES = {FORUM_THREAD_TYPE_NOVEL, FORUM_THREAD_TYPE_GENERAL}
FORUM_COMMENT_REACTION_LIKE = "like"
FORUM_COMMENT_REACTION_DISLIKE = "dislike"
FORUM_COMMENT_REACTION_CLEAR = "clear"
VALID_FORUM_COMMENT_REACTIONS = {
    FORUM_COMMENT_REACTION_LIKE,
    FORUM_COMMENT_REACTION_DISLIKE,
    FORUM_COMMENT_REACTION_CLEAR,
}
PUBLIC_DEMO_SOURCE_KIND = "public_demo"
USER_PUBLIC_SHARE_SOURCE_KIND = "user_public_share"
PUBLIC_FORUM_STATUS_DISABLED = "disabled"
PUBLIC_FORUM_STATUS_INTERNAL = "internal"
PUBLIC_FORUM_STATUS_BETA = "beta"
PUBLIC_FORUM_STATUS_PUBLIC = "public"
PUBLIC_SHARE_STATUS_NOT_REQUESTED = "not_requested"
PUBLIC_SHARE_STATUS_PENDING = "pending"
PUBLIC_SHARE_STATUS_APPROVED = "approved"
VALID_PUBLIC_FORUM_STATUSES = {
    PUBLIC_FORUM_STATUS_DISABLED,
    PUBLIC_FORUM_STATUS_INTERNAL,
    PUBLIC_FORUM_STATUS_BETA,
    PUBLIC_FORUM_STATUS_PUBLIC,
}
VALID_PUBLIC_SHARE_STATUSES = {
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    PUBLIC_SHARE_STATUS_APPROVED,
}
DEFAULT_PUBLIC_FORUM_PAGE_SIZE = 20
MAX_PUBLIC_FORUM_PAGE_SIZE = 100
GENERAL_PUBLIC_FORUM_DAILY_POST_LIMIT = 5
MAX_PUBLIC_FORUM_IMAGE_BYTES = 5 * 1024 * 1024
PUBLIC_STATUS_DRAFT = "draft"
PUBLIC_STATUS_PENDING_REVIEW = "pending_review"
PUBLIC_STATUS_PUBLISHED = "published"
PUBLIC_STATUS_HIDDEN = "hidden"
PUBLIC_STATUS_REMOVED = "removed"
MODERATION_STATUS_CLEAN = "clean"
MODERATION_STATUS_REPORTED = "reported"
MODERATION_STATUS_UNDER_REVIEW = "under_review"
MODERATION_STATUS_HIDDEN = "hidden"
MODERATION_STATUS_REMOVED = "removed"
CONTENT_SOURCE_TYPE_USER_ORIGINAL = "user_original"
CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN = "public_domain"
CONTENT_SOURCE_TYPE_LICENSED = "licensed"
CONTENT_SOURCE_TYPE_ADMIN_SEEDED = "admin_seeded"
REPORT_TYPE_COPYRIGHT = "copyright"
REPORT_TYPE_PLAGIARISM = "plagiarism"
REPORT_TYPE_IMPERSONATION = "impersonation"
REPORT_TYPE_SPAM = "spam"
REPORT_TYPE_ILLEGAL_CONTENT = "illegal_content"
REPORT_TYPE_HARASSMENT = "harassment"
REPORT_TYPE_OTHER = "other"
REPORT_STATUS_OPEN = "open"
REPORT_STATUS_TRIAGED = "triaged"
REPORT_STATUS_CONTENT_HIDDEN = "content_hidden"
REPORT_STATUS_REJECTED = "rejected"
REPORT_STATUS_RESOLVED = "resolved"
STRIKE_SEVERITY_LOW = "low"
STRIKE_SEVERITY_MEDIUM = "medium"
STRIKE_SEVERITY_HIGH = "high"
STRIKE_SEVERITY_CRITICAL = "critical"
VALID_PUBLIC_STATUSES = {
    PUBLIC_STATUS_DRAFT,
    PUBLIC_STATUS_PENDING_REVIEW,
    PUBLIC_STATUS_PUBLISHED,
    PUBLIC_STATUS_HIDDEN,
    PUBLIC_STATUS_REMOVED,
}
VALID_MODERATION_STATUSES = {
    MODERATION_STATUS_CLEAN,
    MODERATION_STATUS_REPORTED,
    MODERATION_STATUS_UNDER_REVIEW,
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REMOVED,
}
VALID_CONTENT_SOURCE_TYPES = {
    CONTENT_SOURCE_TYPE_USER_ORIGINAL,
    CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN,
    CONTENT_SOURCE_TYPE_LICENSED,
    CONTENT_SOURCE_TYPE_ADMIN_SEEDED,
}
VALID_REPORT_TYPES = {
    REPORT_TYPE_COPYRIGHT,
    REPORT_TYPE_PLAGIARISM,
    REPORT_TYPE_IMPERSONATION,
    REPORT_TYPE_SPAM,
    REPORT_TYPE_ILLEGAL_CONTENT,
    REPORT_TYPE_HARASSMENT,
    REPORT_TYPE_OTHER,
}
VALID_REPORT_STATUSES = {
    REPORT_STATUS_OPEN,
    REPORT_STATUS_TRIAGED,
    REPORT_STATUS_CONTENT_HIDDEN,
    REPORT_STATUS_REJECTED,
    REPORT_STATUS_RESOLVED,
}
SERIOUS_STRIKE_SEVERITIES = {STRIKE_SEVERITY_HIGH, STRIKE_SEVERITY_CRITICAL}
PUBLIC_PUBLISH_LIMIT_NEW_USER = 1
PUBLIC_PUBLISH_LIMIT_STANDARD = 3
PUBLIC_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PUBLIC_ANALYTICS_EVENT_BOOK_VIEW = "book_view"
PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW = "chapter_view"
VALID_PUBLIC_ANALYTICS_EVENT_TYPES = {
    PUBLIC_ANALYTICS_EVENT_BOOK_VIEW,
    PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW,
}
PUBLIC_FORUM_IMAGE_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG": ("png", "image/png"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),
}


def hash_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_public_visitor_fingerprint(request: Request | None) -> str | None:
    if request is None:
        return None
    client_host = trusted_client_ip(request) or ""
    user_agent = " ".join(str(request.headers.get("user-agent") or "").split()).strip().lower()
    fingerprint_source = "|".join(part for part in (client_host, user_agent) if part)
    return hash_text(fingerprint_source)


def _form_text(form: Any, key: str, default: str | None = None) -> str | None:
    value = form.get(key)
    if value is None:
        return default
    return str(value)


def _form_bool(form: Any, key: str, default: bool = False) -> bool:
    raw = _form_text(form, key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _form_int(form: Any, key: str) -> int | None:
    raw = _form_text(form, key)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError:
        raise HTTPException(422, f"{key} must be a whole number.")


def _form_upload(form: Any, key: str) -> UploadFile | None:
    value = form.get(key)
    if value is None or not hasattr(value, "filename"):
        return None
    filename = str(getattr(value, "filename", "") or "").strip()
    return value if filename else None


def _json_payload_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(422, "Request body must be a JSON object.")
    return payload


async def parse_public_forum_post_create_request(
    request: Request,
) -> tuple[PublicForumPostCreateBody, UploadFile | None]:
    content_type = str(request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        try:
            return PublicForumPostCreateBody(
                thread_type=_form_text(form, "thread_type", "novel") or "novel",
                book_id=_form_text(form, "book_id") or None,
                headline=_form_text(form, "headline", "") or "",
                body=_form_text(form, "body", "") or "",
                desired_beta_reader_count=_form_int(form, "desired_beta_reader_count"),
                allow_contact_requests=_form_bool(form, "allow_contact_requests", True),
            ), _form_upload(form, "image")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    try:
        return PublicForumPostCreateBody(**_json_payload_dict(await request.json())), None
    except ValueError as exc:
        raise HTTPException(422, str(exc))


async def parse_public_forum_post_update_request(
    request: Request,
) -> tuple[PublicForumPostUpdateBody, UploadFile | None]:
    content_type = str(request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        try:
            return PublicForumPostUpdateBody(
                thread_type=_form_text(form, "thread_type", "novel") or "novel",
                headline=_form_text(form, "headline", "") or "",
                body=_form_text(form, "body", "") or "",
                desired_beta_reader_count=_form_int(form, "desired_beta_reader_count"),
                allow_contact_requests=_form_bool(form, "allow_contact_requests", True),
                status=_form_text(form, "status", "open") or "open",
                remove_image=_form_bool(form, "remove_image", False),
            ), _form_upload(form, "image")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    try:
        return PublicForumPostUpdateBody(**_json_payload_dict(await request.json())), None
    except ValueError as exc:
        raise HTTPException(422, str(exc))


async def parse_public_forum_comment_create_request(
    request: Request,
) -> tuple[PublicForumCommentCreateBody, UploadFile | None]:
    content_type = str(request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        try:
            return PublicForumCommentCreateBody(
                body=_form_text(form, "body", "") or "",
                parent_comment_id=_form_text(form, "parent_comment_id") or None,
            ), _form_upload(form, "image")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    try:
        return PublicForumCommentCreateBody(**_json_payload_dict(await request.json())), None
    except ValueError as exc:
        raise HTTPException(422, str(exc))


async def _read_public_forum_image(upload: UploadFile) -> tuple[bytes, str, str]:
    parts: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_PUBLIC_FORUM_IMAGE_BYTES:
            raise HTTPException(413, "Forum image exceeds the maximum allowed size (5 MB).")
        parts.append(chunk)
    raw = b"".join(parts)
    await upload.seek(0)
    if not raw:
        raise HTTPException(400, "Forum image cannot be empty.")
    for magic, (suffix, mime) in PUBLIC_FORUM_IMAGE_MAGIC.items():
        if raw[: len(magic)] == magic:
            if mime == "image/webp" and raw[8:12] != b"WEBP":
                continue
            return raw, suffix, mime
    raise HTTPException(400, "Forum image must be a JPEG, PNG, GIF, or WebP file.")


def _safe_forum_image_filename(upload: UploadFile, suffix: str) -> str:
    safe_name = Path(str(upload.filename or "")).name.strip()
    if not safe_name:
        return f"forum-image.{suffix}"
    stem = Path(safe_name).stem.strip() or "forum-image"
    return f"{stem[:80]}.{suffix}"


async def store_public_forum_image(
    upload: UploadFile,
    *,
    owner_user_id: uuid.UUID,
    target_kind: str,
    target_id: uuid.UUID,
) -> tuple[str, str, str]:
    raw, suffix, mime = await _read_public_forum_image(upload)
    filename = _safe_forum_image_filename(upload, suffix)
    storage_key = (
        f"public-forum/{owner_user_id}/{target_kind}/{target_id}/{uuid.uuid4().hex}.{suffix}"
    )
    await asyncio.to_thread(upload_binary, storage_key, raw, mime)
    return storage_key, mime, filename


def public_forum_image_url(
    *,
    storage_key: str | None,
    owner_user_id: uuid.UUID,
    target_kind: str,
    target_id: uuid.UUID,
) -> str | None:
    if not storage_key:
        return None
    presigned = get_presigned_url(storage_key)
    if presigned:
        return presigned
    token = create_asset_token(
        str(owner_user_id),
        f"public-forum-{target_kind}-image:{target_id}",
        expires_minutes=120,
    )
    return f"{settings.API_V1_PREFIX}/public/forum/{target_kind}s/{target_id}/image?token={token}"


async def get_public_forum_image_response(
    db: AsyncSession,
    *,
    target_kind: str,
    target_id: uuid.UUID,
    token: str,
) -> Response:
    if target_kind == "post":
        target = await db.get(BookForumPost, target_id)
        missing_message = "Forum post image not found."
    elif target_kind == "comment":
        target = await db.get(BookForumComment, target_id)
        missing_message = "Forum comment image not found."
    else:
        raise HTTPException(404, "Forum image not found.")

    if target is None or not getattr(target, "image_s3_key", None):
        raise HTTPException(404, missing_message)

    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "asset"
        or payload.get("sub") != str(target.author_user_id)
        or payload.get("res") != f"public-forum-{target_kind}-image:{target.id}"
    ):
        raise HTTPException(401, "Invalid forum image token")

    try:
        raw = await asyncio.to_thread(download_book, target.image_s3_key)
    except STORAGE_IO_EXCEPTIONS:
        raise HTTPException(404, missing_message)
    return Response(content=raw, media_type=target.image_content_type or "application/octet-stream")
