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
    title: str
    author: str | None = None
    author_username: str | None = None
    genre: str | None = None
    description: str | None = None
    format: str
    work_type: str
    status: str
    total_chapters: int | None = None
    copyright_warning: bool = False
    created_at: datetime | None = None


class PublicBookChapterMetaOut(BaseModel):
    number: int
    title: str | None = None
    description: str | None = None


class PublicBookDetailOut(PublicBookOut):
    chapters: list[PublicBookChapterMetaOut] = Field(default_factory=list)


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


class PublicChapterAppendOut(BaseModel):
    book_id: str
    chapter_number: int
    saved: bool


class PublicForumRatingSummaryOut(BaseModel):
    average_rating: float | None = None
    rating_count: int = 0
    positive_rating_count: int = 0
    neutral_rating_count: int = 0
    negative_rating_count: int = 0


class PublicForumPostCreateBody(BaseModel):
    book_id: uuid.UUID
    headline: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=20, max_length=5000)
    desired_beta_reader_count: int | None = Field(default=None, ge=1, le=500)
    allow_contact_requests: bool = True


class PublicForumPostUpdateBody(BaseModel):
    headline: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=20, max_length=5000)
    desired_beta_reader_count: int | None = Field(default=None, ge=1, le=500)
    allow_contact_requests: bool = True
    status: str = Field(default="open", min_length=4, max_length=32)


class PublicForumPostOut(BaseModel):
    id: str
    book_id: str
    author_user_id: str
    author_username: str | None = None
    author_reputation_score: int = 0
    author_trust_level: str
    title: str
    author: str | None = None
    genre: str | None = None
    work_type: str
    headline: str
    body: str
    desired_beta_reader_count: int | None = None
    allow_contact_requests: bool
    status: str
    interest_count: int = 0
    comment_count: int = 0
    rating_summary: PublicForumRatingSummaryOut
    discoverability_score: float
    created_at: datetime
    updated_at: datetime


class PublicForumPostListOut(BaseModel):
    items: list[PublicForumPostOut]


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


class PublicForumCommentReactionBody(BaseModel):
    reaction: str = Field(..., min_length=4, max_length=8)


class PublicForumCommentOut(BaseModel):
    id: str
    post_id: str
    book_id: str
    author_user_id: str
    author_username: str | None = None
    author_reputation_score: int = 0
    author_trust_level: str
    body: str
    like_count: int = 0
    dislike_count: int = 0
    reaction: str | None = None
    can_edit: bool = False
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
    created_at: datetime
