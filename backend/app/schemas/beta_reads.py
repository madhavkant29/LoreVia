from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BetaReadAssignmentCreateBody(BaseModel):
    reader_email: str = Field(..., min_length=3, max_length=320)
    task_label: str = Field(..., min_length=3, max_length=200)
    scope_kind: str = Field(default="full_book", max_length=32)
    section_label: str | None = Field(default=None, max_length=200)
    chapter_start: int | None = Field(default=None, ge=1)
    chapter_end: int | None = Field(default=None, ge=1)
    window_days: int = Field(..., ge=3, le=7)
    reward_points: int = Field(..., ge=1, le=100000)
    required_progress_pct: int = Field(default=100, ge=1, le=100)
    required_comment_count: int = Field(default=0, ge=0, le=1000)
    required_feedback_item_count: int = Field(default=1, ge=1, le=1000)
    require_final_feedback: bool = True
    starts_at: datetime | None = None
    author_questions: list[str] = Field(default_factory=list, max_length=12)


class BetaReadAssignmentOut(BaseModel):
    id: str
    book_id: str
    author_user_id: str
    reader_user_id: str | None = None
    reader_email: str
    collaborator_id: str | None = None
    state: str
    view_bucket: str
    task_label: str
    scope_kind: str
    section_label: str | None = None
    chapter_start: int | None = None
    chapter_end: int | None = None
    window_days: int
    reward_points: int
    projected_reward_points: int
    awarded_points: int
    required_progress_pct: int
    required_comment_count: int
    required_feedback_item_count: int
    require_final_feedback: bool
    starts_at: datetime
    expires_at: datetime
    access_granted_at: datetime
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    awarded_at: datetime | None = None
    first_opened_at: datetime | None = None
    missed_reason: str | None = None
    counted_toward_missed_streak: bool = False
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    disqualified_at: datetime | None = None
    disqualified_reason: str | None = None
    book_title: str
    author_name: str
    book_route_title: str
    progress_pct: float
    chapters_total: int
    chapters_read_count: int
    comment_count: int
    feedback_item_count: int
    question_count: int
    answered_question_count: int
    current_chapter: int
    status_label: str
    primary_action: str
    submission_allowed: bool
    is_overdue: bool
    consecutive_missed_beta_reads: int
    penalty_status: str
    penalty_warning: str | None = None
    final_rating: float | None = None
    rating_sentiment: str | None = None
    book_average_rating: float | None = None
    book_rating_count: int = 0


class BetaReadAssignmentListOut(BaseModel):
    items: list[BetaReadAssignmentOut]


class BetaReadFeedbackSubmitBody(BaseModel):
    final_feedback: str = Field(..., min_length=3, max_length=20000)
    final_rating: float = Field(..., ge=1, le=5)


class BetaReadQuestionAppendBody(BaseModel):
    questions: list[str] = Field(..., min_length=1, max_length=12)


class BetaReadQuestionOut(BaseModel):
    id: str
    prompt: str
    created_at: datetime
    answer_count: int = 0


class BetaReadFeedbackItemCreateBody(BaseModel):
    kind: str = Field(..., min_length=3, max_length=32)
    chapter_number: int | None = Field(default=None, ge=1)
    scene_id: str | None = None
    question_id: str | None = None
    reaction: str | None = Field(default=None, max_length=64)
    anchor_text: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=10000)


class BetaReadFeedbackItemOut(BaseModel):
    id: str
    kind: str
    chapter_number: int | None = None
    scene_id: str | None = None
    scene_title: str | None = None
    question_id: str | None = None
    question_prompt: str | None = None
    reaction: str | None = None
    anchor_text: str | None = None
    body: str | None = None
    created_at: datetime
    updated_at: datetime


class BetaReadFeedbackSummaryOut(BaseModel):
    feedback_item_count: int = 0
    chapter_comment_count: int = 0
    scene_reaction_count: int = 0
    answer_count: int = 0
    confusing_count: int = 0
    boring_count: int = 0
    favorite_count: int = 0


class BetaReadAssignmentDetailOut(BaseModel):
    assignment: BetaReadAssignmentOut
    author_questions: list[BetaReadQuestionOut]
    feedback_items: list[BetaReadFeedbackItemOut]
    feedback_summary: BetaReadFeedbackSummaryOut


class BetaReadSyncOut(BaseModel):
    assignment: BetaReadAssignmentOut


class BetaReadJobRunOut(BaseModel):
    reminders_sent: int = 0
    expired_count: int = 0
    missed_count: int = 0
    completed_count: int = 0
