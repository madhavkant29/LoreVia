import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.core.redis import (
    cache_get,
    cache_get_int,
    cache_set,
    get_public_forum_comments_cache,
    key_public_forum_cache_version,
    key_public_forum_post_detail,
    key_public_forum_posts,
    set_public_forum_comments_cache,
)
from app.schemas.public import (
    PublicForumCommentListOut,
    PublicForumCommentOut,
    PublicForumCommentReactionBody,
    PublicForumInterestCreateBody,
    PublicForumInterestListOut,
    PublicForumInterestOut,
    PublicForumPostListOut,
    PublicForumPostOut,
    PublicForumPostReactionBody,
)
from app.utils.public.forum_engagement import (
    create_public_forum_comment,
    create_public_forum_interest,
    list_public_forum_comments,
    list_public_forum_interests_for_author,
    react_to_public_forum_comment,
    react_to_public_forum_post,
)
from app.utils.public.forum_foundation import (
    ensure_public_forum_read_enabled,
    ensure_public_forum_write_enabled,
)
from app.utils.public.forum_posts import (
    create_public_forum_post,
    get_public_forum_post_detail,
    list_author_public_forum_posts,
    list_public_forum_posts,
    update_public_forum_post,
)
from app.utils.public.requests import (
    get_public_forum_image_response,
    parse_public_forum_comment_create_request,
    parse_public_forum_post_create_request,
    parse_public_forum_post_update_request,
)
from app.utils.public_utils import (
    DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
    MAX_PUBLIC_FORUM_PAGE_SIZE,
)

router = APIRouter()


@router.get("/forum/posts", response_model=PublicForumPostListOut)
async def list_public_beta_forum_posts(
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=DEFAULT_PUBLIC_FORUM_PAGE_SIZE, ge=1, le=MAX_PUBLIC_FORUM_PAGE_SIZE
    ),
    thread_type: str | None = Query(default=None, pattern=r"^(general|novel)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_forum_read_enabled()
    normalized_query = " ".join((q or "").split()).strip()
    normalized_thread_type = thread_type if isinstance(thread_type, str) else None
    if current_user is None:
        version = await cache_get_int(key_public_forum_cache_version(), default=1)
        cache_key = key_public_forum_posts(
            version, normalized_query, page, page_size, normalized_thread_type
        )
        cached = await cache_get(cache_key)
        if cached:
            return PublicForumPostListOut(**cached)

    payload = await list_public_forum_posts(
        db,
        q=normalized_query,
        page=page,
        page_size=page_size,
        thread_type=normalized_thread_type,
        current_user=current_user,
    )
    if current_user is None:
        await cache_set(cache_key, payload.model_dump(mode="json"), 120)
    return payload


@router.get("/forum/my-posts", response_model=list[PublicForumPostOut])
async def list_current_author_public_forum_posts(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_read_enabled()
    return await list_author_public_forum_posts(db, author_user_id=current_user.id)


@router.get("/forum/posts/{post_id}", response_model=PublicForumPostOut)
async def get_public_beta_forum_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_forum_read_enabled()
    if current_user is None:
        version = await cache_get_int(key_public_forum_cache_version(), default=1)
        cache_key = key_public_forum_post_detail(version, str(post_id))
        cached = await cache_get(cache_key)
        if cached:
            return PublicForumPostOut(**cached)

    payload = await get_public_forum_post_detail(
        db,
        post_id=post_id,
        current_user=current_user,
    )
    if current_user is None:
        await cache_set(cache_key, payload.model_dump(mode="json"), 120)
    return payload


@router.post("/forum/posts", response_model=PublicForumPostOut, status_code=201)
async def create_public_beta_forum_post_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    body, image_upload = await parse_public_forum_post_create_request(request)
    return await create_public_forum_post(
        db, current_user=current_user, body=body, image_upload=image_upload
    )


@router.put("/forum/posts/{post_id}", response_model=PublicForumPostOut)
async def edit_public_beta_forum_post_endpoint(
    post_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    body, image_upload = await parse_public_forum_post_update_request(request)
    return await update_public_forum_post(
        db, post_id=post_id, current_user=current_user, body=body, image_upload=image_upload
    )


@router.get("/forum/posts/{post_id}/image")
async def get_public_forum_post_image(
    post_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    ensure_public_forum_read_enabled()
    return await get_public_forum_image_response(
        db, target_kind="post", target_id=post_id, token=token
    )


@router.post(
    "/forum/posts/{post_id}/interests", response_model=PublicForumInterestOut, status_code=201
)
async def create_public_beta_forum_interest_endpoint(
    post_id: uuid.UUID,
    body: PublicForumInterestCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await create_public_forum_interest(
        db, post_id=post_id, current_user=current_user, body=body
    )


@router.get("/forum/posts/{post_id}/interests", response_model=PublicForumInterestListOut)
async def list_public_beta_forum_interests(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return PublicForumInterestListOut(
        items=await list_public_forum_interests_for_author(
            db,
            post_id=post_id,
            author_user_id=current_user.id,
        )
    )


@router.get("/forum/posts/{post_id}/comments", response_model=PublicForumCommentListOut)
async def list_public_beta_forum_comments(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_forum_read_enabled()
    if current_user is None:
        version = await cache_get_int(key_public_forum_cache_version(), default=1)
        cached = await get_public_forum_comments_cache(version, str(post_id))
        if cached is not None:
            return PublicForumCommentListOut(items=cached)
    payload = PublicForumCommentListOut(
        items=await list_public_forum_comments(
            db,
            post_id=post_id,
            current_user=current_user,
        )
    )
    if current_user is None:
        await set_public_forum_comments_cache(
            version,
            str(post_id),
            [item.model_dump(mode="json") for item in payload.items],
        )
    return payload


@router.post(
    "/forum/posts/{post_id}/comments", response_model=PublicForumCommentOut, status_code=201
)
async def create_public_beta_forum_comment(
    post_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    body, image_upload = await parse_public_forum_comment_create_request(request)
    return await create_public_forum_comment(
        db, post_id=post_id, current_user=current_user, body=body, image_upload=image_upload
    )


@router.get("/forum/comments/{comment_id}/image")
async def get_public_forum_comment_image(
    comment_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    ensure_public_forum_read_enabled()
    return await get_public_forum_image_response(
        db, target_kind="comment", target_id=comment_id, token=token
    )


@router.put("/forum/posts/{post_id}/reaction", response_model=PublicForumPostOut)
async def react_to_public_beta_forum_post(
    post_id: uuid.UUID,
    body: PublicForumPostReactionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await react_to_public_forum_post(
        db,
        post_id=post_id,
        current_user=current_user,
        reaction=body.reaction,
    )


@router.put("/forum/comments/{comment_id}/reaction", response_model=PublicForumCommentOut)
async def react_to_public_beta_forum_comment(
    comment_id: uuid.UUID,
    body: PublicForumCommentReactionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await react_to_public_forum_comment(
        db,
        comment_id=comment_id,
        current_user=current_user,
        reaction=body.reaction,
    )
