import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user, get_optional_current_user
from app.api.v1.routes.public_catalog import (
    get_public_book,
    get_public_chapter,
    get_public_uploads_analytics,
    get_public_user_profile_endpoint,
    list_creator_public_uploads,
    list_public_books,
    list_ranked_creator_public_uploads,
    list_ranked_public_beta_novels_endpoint,
    record_public_book_view,
)
from app.api.v1.routes.public_catalog import router as catalog_router
from app.api.v1.routes.public_forum import (
    create_public_beta_forum_comment,
    create_public_beta_forum_interest_endpoint,
    create_public_beta_forum_post_endpoint,
    edit_public_beta_forum_post_endpoint,
    get_public_beta_forum_post,
    get_public_forum_comment_image,
    get_public_forum_post_image,
    list_current_author_public_forum_posts,
    list_public_beta_forum_comments,
    list_public_beta_forum_interests,
    list_public_beta_forum_posts,
    react_to_public_beta_forum_comment,
    react_to_public_beta_forum_post,
)
from app.api.v1.routes.public_forum import router as forum_router
from app.api.v1.routes.public_shared import (
    get_user_shared_book,
    get_user_shared_chapter,
    list_user_shared_books,
    publish_user_shared_book,
    unpublish_user_shared_book,
)
from app.api.v1.routes.public_shared import router as shared_router
from app.core.database import get_db
from app.core.redis import (
    cache_del,
    cache_get,
    cache_get_int,
    cache_set,
    get_public_forum_comments_cache,
    key_public_book_detail,
    key_public_books,
    key_public_chapter,
    key_public_forum_cache_version,
    key_public_forum_post_detail,
    key_public_forum_posts,
    mark_public_profile_cache_dirty,
    set_public_forum_comments_cache,
)
from app.core.storage import download_book, get_presigned_url
from app.models.book import Book, Chapter
from app.models.user import User
from app.schemas.public import (
    PublicBookAnalyticsOut,
    PublicBookAnalyticsViewBody,
    PublicBookCreateOut,
    PublicBookDetailOut,
    PublicBookListOut,
    PublicBookOut,
    PublicBookShareBody,
    PublicChapterOut,
    PublicForumCommentListOut,
    PublicForumCommentOut,
    PublicForumCommentReactionBody,
    PublicForumInterestCreateBody,
    PublicForumInterestListOut,
    PublicForumInterestOut,
    PublicForumPostListOut,
    PublicForumPostOut,
    PublicForumPostReactionBody,
    PublicRankedBookListOut,
    PublicUploadsOverviewOut,
    PublicUserProfileOut,
)
from app.services.public_publish_service import submit_public_share
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
)
from app.utils.compliance.copyright_check import evaluate_document_copyright
from app.utils.public.analytics import (
    build_public_book_analytics,
    build_public_book_analytics_map,
    build_public_uploads_overview,
    list_visible_creator_public_book_outs,
    record_public_book_analytics_event,
)
from app.utils.public.catalog import (
    _active_forum_post_map,
    _get_public_book_by_slug_or_id,
    filter_public_books_catalog,
    is_catalog_visible_public_book,
)
from app.utils.public.content import (
    append_public_chapter,
    create_public_book_manual,
    normalize_public_slug,
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
from app.utils.public.profiles import get_public_user_profile
from app.utils.public.ranking_core import (
    normalize_public_ranking_key,
    normalize_public_ranking_window,
)
from app.utils.public.ranking_service import (
    list_ranked_public_beta_novels,
    list_ranked_public_uploads,
)
from app.utils.public.requests import (
    get_public_forum_image_response,
    parse_public_forum_comment_create_request,
    parse_public_forum_post_create_request,
    parse_public_forum_post_update_request,
)
from app.utils.public.serialization import (
    build_public_book_out,
    can_owner_or_admin_view_hidden_book,
    can_view_public_book,
    ensure_public_authoring_access,
    ensure_public_mode_enabled,
    get_public_share_status,
    is_admin_user,
    is_approved_user_public_share_book,
    is_public_demo_book,
    is_user_public_share_book,
    public_visibility_notice,
    resolve_optional_user,
)
from app.utils.public_utils import (
    CONTENT_SOURCE_TYPE_ADMIN_SEEDED,
    DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
    FORUM_POST_OPEN,
    FORUM_THREAD_TYPE_NOVEL,
    MAX_PUBLIC_FORUM_PAGE_SIZE,
    PUBLIC_DEMO_SOURCE_KIND,
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    PUBLIC_STATUS_PUBLISHED,
    USER_PUBLIC_SHARE_SOURCE_KIND,
)

router = APIRouter()
router.include_router(forum_router)
router.include_router(catalog_router)
router.include_router(shared_router)

__all__ = ["router"]


import importlib
import sys
from types import ModuleType

_PATCH_TARGET_MODULES = tuple(
    importlib.import_module(module_name)
    for module_name in (
        "app.api.v1.routes.public_forum",
        "app.api.v1.routes.public_catalog",
        "app.api.v1.routes.public_shared",
    )
)


class _PatchPropagatingModule(ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for target_module in _PATCH_TARGET_MODULES:
            if hasattr(target_module, name):
                setattr(target_module, name, value)


sys.modules[__name__].__class__ = _PatchPropagatingModule
