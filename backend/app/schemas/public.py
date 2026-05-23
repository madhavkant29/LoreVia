from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PublicChapterIn(BaseModel):
    title: str
    text: str
    description: str | None = None


class PublicBookManualIn(BaseModel):
    title: str
    author: str | None = None
    genre: str | None = None
    description: str | None = None
    chapters: list[PublicChapterIn]


class PublicBookOut(BaseModel):
    id: str
    public_kind: str | None = None
    public_slug: str | None = None
    title: str
    author: str | None = None
    author_username: str | None = None
    creator_display_name: str | None = None
    genre: str | None = None
    description: str | None = None
    format: str
    work_type: str
    status: str
    public_status: str = "draft"
    moderation_status: str = "clean"
    content_source_type: str = "user_original"
    source_title: str | None = None
    source_author: str | None = None
    source_public_domain_note: str | None = None
    source_url: str | None = None
    total_chapters: int | None = None
    copyright_warning: bool = False
    active_forum_post_id: str | None = None
    analytics: PublicBookAnalyticsOut | None = None
    created_at: datetime | None = None
    published_at: datetime | None = None


class PublicBookAnalyticsOut(BaseModel):
    book_view_count: int = 0
    unique_reader_count_30d: int = 0
    chapter_view_count: int = 0
    published_at: datetime | None = None
    chapter_count: int = 0
    total_words: int = 0
    has_open_discussion: bool = False
    open_discussion_count: int = 0
    discussion_comment_count: int = 0
    discussion_interest_count: int = 0


class PublicBookChapterMetaOut(BaseModel):
    number: int
    title: str | None = None
    description: str | None = None


class PublicBookDetailOut(PublicBookOut):
    chapters: list[PublicBookChapterMetaOut] = Field(default_factory=list)
    visibility_notice: str | None = None
    analytics: PublicBookAnalyticsOut | None = None


class PublicChapterOut(BaseModel):
    book_id: str
    book_title: str
    chapter_number: int
    chapter_title: str | None = None
    chapter_description: str | None = None
    total_chapters: int | None = None
    text_url: str | None = None
    text_content: str | None = None
    html_content: str | None = None


class PublicBookCreateOut(BaseModel):
    book_id: str
    status: str
    visibility: str
    public_kind: str
    approval_status: str
    public_slug: str | None = None
    message: str | None = None


class PublicBookShareBody(BaseModel):
    public_slug: str | None = Field(default=None, min_length=3, max_length=120)
    rights_confirmation: bool = False
    confirm_public_share: bool = False
    content_source_type: str = Field(default="user_original", min_length=4, max_length=32)
    description: str | None = Field(default=None, max_length=2000)


class PublicBookListOut(BaseModel):
    items: list[PublicBookOut]
    total: int
    page: int
    limit: int
    has_more: bool


class ContentReportCreateBody(BaseModel):
    book_id: uuid.UUID
    report_type: str = Field(..., min_length=3, max_length=64)
    reason: str = Field(..., min_length=5, max_length=5000)
    details: str | None = Field(default=None, max_length=5000)
    reporter_email: str | None = Field(default=None, max_length=320)
    copyright_owner_name: str | None = Field(default=None, max_length=255)
    copyright_work_description: str | None = Field(default=None, max_length=5000)
    copyright_original_url: str | None = Field(default=None, max_length=2000)
    reported_content_url: str | None = Field(default=None, max_length=2000)


class ContentReportOut(BaseModel):
    id: str
    status: str
    report_type: str
    reported_book_id: str
    created_at: datetime
    message: str | None = None


class PublicChapterAppendOut(BaseModel):
    book_id: str
    chapter_number: int
    saved: bool


class PublicBookAnalyticsViewBody(BaseModel):
    event_type: str = Field(..., min_length=4, max_length=32)
    chapter_number: int | None = Field(default=None, ge=1)


class PublicForumRatingSummaryOut(BaseModel):
    average_rating: float | None = None
    rating_count: int = 0
    positive_rating_count: int = 0
    neutral_rating_count: int = 0
    negative_rating_count: int = 0


class PublicForumPostCreateBody(BaseModel):
    thread_type: str = Field(default="novel", min_length=5, max_length=16)
    book_id: uuid.UUID | None = None
    headline: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=20, max_length=5000)
    desired_beta_reader_count: int | None = Field(default=None, ge=1, le=500)
    allow_contact_requests: bool = True


class PublicForumPostUpdateBody(BaseModel):
    thread_type: str = Field(default="novel", min_length=5, max_length=16)
    headline: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=20, max_length=5000)
    desired_beta_reader_count: int | None = Field(default=None, ge=1, le=500)
    allow_contact_requests: bool = True
    status: str = Field(default="open", min_length=4, max_length=32)


class PublicForumPostOut(BaseModel):
    id: str
    thread_type: str
    book_id: str | None = None
    author_user_id: str
    author_username: str | None = None
    author_reputation_score: int = 0
    author_trust_level: str
    title: str | None = None
    author: str | None = None
    genre: str | None = None
    description: str | None = None
    work_type: str | None = None
    headline: str
    body: str
    desired_beta_reader_count: int | None = None
    allow_contact_requests: bool
    status: str
    viewer_interest_status: str | None = None
    reaction: str | None = None
    interest_count: int = 0
    comment_count: int = 0
    like_count: int = 0
    dislike_count: int = 0
    rating_summary: PublicForumRatingSummaryOut
    discoverability_score: float
    created_at: datetime
    updated_at: datetime


class PublicForumPostListOut(BaseModel):
    items: list[PublicForumPostOut]
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class PublicForumInterestCreateBody(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)


class PublicForumInterestOut(BaseModel):
    id: str
    post_id: str
    book_id: str
    author_user_id: str
    interested_user_id: str
    interested_username: str | None = None
    interested_email: str
    message: str
    status: str
    created_at: datetime
    updated_at: datetime


class PublicForumInterestListOut(BaseModel):
    items: list[PublicForumInterestOut]


class PublicForumCommentCreateBody(BaseModel):
    body: str = Field(..., min_length=2, max_length=5000)
    parent_comment_id: uuid.UUID | None = None


class PublicForumPostReactionBody(BaseModel):
    reaction: str = Field(..., min_length=4, max_length=8)


class PublicForumCommentReactionBody(BaseModel):
    reaction: str = Field(..., min_length=4, max_length=8)


class PublicForumCommentOut(BaseModel):
    id: str
    post_id: str
    book_id: str | None = None
    parent_comment_id: str | None = None
    author_user_id: str
    author_username: str | None = None
    author_reputation_score: int = 0
    author_trust_level: str
    body: str
    like_count: int = 0
    dislike_count: int = 0
    reaction: str | None = None
    can_edit: bool = False
    replies: list["PublicForumCommentOut"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PublicForumCommentListOut(BaseModel):
    items: list[PublicForumCommentOut]


class PublicUserProjectOut(BaseModel):
    book_id: str
    title: str
    genre: str | None = None
    description: str | None = None
    progress_words: int = 0
    source: str
    forum_post_id: str | None = None
    public_book_id: str | None = None


class PublicAuthorAnalyticsOut(BaseModel):
    total_book_views: int = 0
    total_unique_readers_30d: int = 0
    total_chapter_views: int = 0
    total_public_books: int = 0
    total_chapters: int = 0
    total_words: int = 0
    latest_published_at: datetime | None = None
    open_forum_discussions_count: int = 0


class PublicUploadsBreakdownEntryOut(BaseModel):
    key: str
    label: str
    count: int = 0


class PublicUploadsOverviewOut(BaseModel):
    total_public_books: int = 0
    total_authors: int = 0
    total_visible_chapters: int = 0
    total_visible_words: int = 0
    uploads_last_30_days: int = 0
    genre_breakdown: list[PublicUploadsBreakdownEntryOut] = Field(default_factory=list)
    work_type_breakdown: list[PublicUploadsBreakdownEntryOut] = Field(default_factory=list)
    recent_uploads: list[PublicBookOut] = Field(default_factory=list)


class PublicUserActivityPostOut(BaseModel):
    id: str
    thread_type: str
    status: str
    headline: str
    body: str
    title: str | None = None
    genre: str | None = None
    work_type: str | None = None
    book_id: str | None = None
    comment_count: int = 0
    interest_count: int = 0
    like_count: int = 0
    dislike_count: int = 0
    created_at: datetime
    updated_at: datetime


class PublicUserActivityCommentOut(BaseModel):
    id: str
    post_id: str
    thread_type: str
    post_status: str
    post_headline: str
    post_title: str | None = None
    book_id: str | None = None
    body: str
    like_count: int = 0
    dislike_count: int = 0
    created_at: datetime
    updated_at: datetime


class PublicUserProfileOut(BaseModel):
    user_id: str
    username: str
    reputation_score: int = 0
    reputation_likes_received: int = 0
    reputation_dislikes_received: int = 0
    trust_level: str
    forum_post_count: int = 0
    forum_comment_count: int = 0
    current_project: PublicUserProjectOut | None = None
    public_books_count: int = 0
    public_books: list[PublicBookOut] = Field(default_factory=list)
    public_analytics: PublicAuthorAnalyticsOut = Field(default_factory=PublicAuthorAnalyticsOut)
    posts: list[PublicUserActivityPostOut] = Field(default_factory=list)
    comments: list[PublicUserActivityCommentOut] = Field(default_factory=list)
    created_at: datetime


PublicForumCommentOut.model_rebuild()
