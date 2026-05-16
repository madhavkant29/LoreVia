import type { Page, Route } from "@playwright/test"
import type { Character } from "@/types/character"

type SessionMode = "authenticated" | "guest"
type LoginMode = "success" | "unauthorized"

type MockOptions = {
  session?: SessionMode
  login?: LoginMode
}

function normalizeMockApiPath(pathname: string) {
  return pathname
    .replace(/^\/api\/v1\/books\/[^/]+--([^/]+)(?=\/|$)/, "/api/v1/books/$1")
    .replace(/^\/api\/v1\/reader\/[^/]+--([^/]+)(?=\/|$)/, "/api/v1/reader/$1")
    .replace(/^\/api\/v1\/intelligence\/[^/]+--([^/]+)(?=\/|$)/, "/api/v1/intelligence/$1")
}

const user = {
  id: "user-1",
  email: "author@getlorevia.com",
  username: "author",
  tier: "author",
  plan_tier: "author",
  tier_label: "Author",
  trial_active: false,
  trial_ends_at: null,
  reading_mode: "analyst",
  daily_word_goal: 1200,
  today_word_count: 450,
  last_login_at: "2026-05-08T10:00:00Z",
  login_streak_days: 7,
  longest_login_streak_days: 12,
  login_activity_dates: ["2026-05-05", "2026-05-06", "2026-05-07", "2026-05-08"],
  email_verified: true,
  created_at: "2026-04-01T09:00:00Z",
}

const book = {
  id: "book-1",
  title: "Sky of Ash",
  author: "M. Vale",
  genre: "Epic Fantasy",
  format: "docx",
  work_type: "novel",
  status: "ready",
  mode: "author",
  source_kind: "upload",
  preserve_chapter_numbers: true,
  cover_url: null,
  total_chapters: 3,
  total_tokens: 42000,
  total_words: 31500,
  is_truncated: false,
  primary_series_id: null,
  series_name: "Ash Cycle",
  series_order: 1,
  is_public: false,
  public_description: null,
  copyright_warning: false,
  archived_at: null,
  hidden_at: null,
  created_at: "2026-05-07T12:00:00Z",
  progress_pct: 64,
  chapters_read_count: 2,
  chapters_left: 1,
  marked_complete_in_series: false,
  processing: {
    status: "ready",
    stage: "ready",
    progress_pct: 100,
    chapters_completed: 3,
    chapters_total: 3,
    eta_seconds: 0,
    last_chapter_number: 2,
    last_chapter_title: "The Ember Gate",
    started_at: "2026-05-07T12:00:00Z",
    updated_at: "2026-05-08T11:45:00Z",
    last_error: null,
  },
}

const publicForumPosts = [
  {
    id: "forum-post-1",
    book_id: "book-1",
    author_user_id: "user-1",
    author_username: "author",
    author_reputation_score: 18,
    author_trust_level: "Trusted",
    title: "Sky of Ash",
    author: "M. Vale",
    genre: "Epic Fantasy",
    work_type: "novel",
    headline: "Looking for sharp beta readers for an ash-storm fantasy.",
    body: "I need readers who can flag pacing drift, trust weak scenes, and tell me where momentum slips before the midpoint.",
    desired_beta_reader_count: 5,
    allow_contact_requests: true,
    status: "open",
    viewer_interest_status: null,
    interest_count: 3,
    comment_count: 2,
    rating_summary: {
      average_rating: 4.6,
      rating_count: 5,
      positive_rating_count: 5,
      neutral_rating_count: 0,
      negative_rating_count: 0,
    },
    discoverability_score: 114,
    created_at: "2026-05-14T08:00:00Z",
    updated_at: "2026-05-14T12:00:00Z",
  },
]

let publicForumComments: Array<{
  id: string
  post_id: string
  book_id: string
  author_user_id: string
  author_username: string | null
  author_reputation_score: number
  author_trust_level: string
  body: string
  like_count: number
  dislike_count: number
  reaction: "like" | "dislike" | null
  can_edit: boolean
  created_at: string
  updated_at: string
}> = [
  {
    id: "forum-comment-1",
    post_id: "forum-post-1",
    book_id: "book-1",
    author_user_id: "reader-1",
    author_username: "beta_reader",
    author_reputation_score: 9,
    author_trust_level: "Trusted",
    body: "The pitch is strong. I’d focus my notes on whether the opening stakes land before chapter two.",
    like_count: 4,
    dislike_count: 0,
    reaction: null,
    can_edit: false,
    created_at: "2026-05-14T09:00:00Z",
    updated_at: "2026-05-14T09:00:00Z",
  },
  {
    id: "forum-comment-2",
    post_id: "forum-post-1",
    book_id: "book-1",
    author_user_id: "reader-2",
    author_username: "line_editor",
    author_reputation_score: 4,
    author_trust_level: "New member",
    body: "I’d also watch how much lore arrives before the first personal conflict turns visible on the page.",
    like_count: 2,
    dislike_count: 0,
    reaction: null,
    can_edit: false,
    created_at: "2026-05-14T09:30:00Z",
    updated_at: "2026-05-14T09:30:00Z",
  },
]

const publicWriterProfiles = {
  author: {
    user_id: "user-1",
    username: "author",
    reputation_score: 18,
    reputation_likes_received: 23,
    reputation_dislikes_received: 5,
    trust_level: "Trusted",
    forum_post_count: 1,
    forum_comment_count: 6,
    current_project: {
      book_id: "book-1",
      title: "Sky of Ash",
      genre: "Epic Fantasy",
      description: "A storm-lashed fantasy about a gate city, a vanished oath, and the cost of holding the wall.",
      progress_words: 20000,
      source: "public_book",
      forum_post_id: null,
      public_book_id: "public-book-1",
    },
    created_at: "2026-04-01T09:00:00Z",
  },
}

const publicBooks = [
  {
    id: "public-book-1",
    title: "Ash Gate Sample",
    author: "M. Vale",
    author_username: "author",
    genre: "Epic Fantasy",
    description: "A safe public sample from the same ash-storm world, shared for readers who want a trust check before joining a beta read.",
    format: "manual",
    work_type: "novel",
    status: "ready",
    total_chapters: 1,
    copyright_warning: false,
    created_at: "2026-05-14T08:00:00Z",
  },
]

const publicBookDetails = {
  "public-book-1": {
    ...publicBooks[0],
    chapters: [
      {
        number: 1,
        title: "The Gate Opens",
        description: "A spoiler-safe sample chapter for public readers.",
      },
    ],
  },
}

const publicChapters = {
  "public-book-1:1": {
    book_id: "public-book-1",
    book_title: "Ash Gate Sample",
    chapter_number: 1,
    chapter_title: "The Gate Opens",
    chapter_description: "A spoiler-safe sample chapter for public readers.",
    total_chapters: 1,
    text_url: null,
    text_content: "Nora crossed the ash gate before the bells could name her.",
    html_content: "<p>Nora crossed the ash gate before the bells could name her.</p>",
  },
}

const initialBetaReads = [
  {
    id: "beta-1",
    book_id: "book-1",
    author_user_id: "user-1",
    reader_user_id: "reader-1",
    reader_email: "reader@example.com",
    collaborator_id: "collab-beta-1",
    state: "in_progress",
    view_bucket: "active",
    task_label: "Chapter 12 feedback",
    scope_kind: "chapter_range",
    section_label: null,
    chapter_start: 12,
    chapter_end: 12,
    window_days: 3,
    required_progress_pct: 100,
    required_comment_count: 3,
    required_feedback_item_count: 3,
    require_final_feedback: true,
    starts_at: "2026-05-13T12:00:00Z",
    expires_at: "2026-05-14T23:59:00Z",
    access_granted_at: "2026-05-13T12:00:00Z",
    submitted_at: null,
    completed_at: null,
    first_opened_at: "2026-05-13T14:00:00Z",
    missed_reason: null,
    counted_toward_missed_streak: false,
    revoked_at: null,
    revoked_reason: null,
    disqualified_at: null,
    disqualified_reason: null,
    book_title: "The Lost Heir",
    author_name: "Seraphina Vale",
    book_route_title: "The Lost Heir",
    progress_pct: 62,
    chapters_total: 1,
    chapters_read_count: 1,
    comment_count: 2,
    feedback_item_count: 2,
    question_count: 2,
    answered_question_count: 1,
    current_chapter: 12,
    status_label: "In progress",
    primary_action: "Continue",
    submission_allowed: false,
    is_overdue: false,
    consecutive_missed_beta_reads: 0,
    penalty_status: "none",
    penalty_warning: null,
  },
  {
    id: "beta-2",
    book_id: "book-1",
    author_user_id: "user-1",
    reader_user_id: "reader-1",
    reader_email: "reader@example.com",
    collaborator_id: "collab-beta-2",
    state: "active",
    view_bucket: "active",
    task_label: "Full beta read",
    scope_kind: "full_book",
    section_label: null,
    chapter_start: null,
    chapter_end: null,
    window_days: 5,
    required_progress_pct: 100,
    required_comment_count: 3,
    required_feedback_item_count: 4,
    require_final_feedback: true,
    starts_at: "2026-05-14T10:00:00Z",
    expires_at: "2026-05-16T23:59:00Z",
    access_granted_at: "2026-05-14T10:00:00Z",
    submitted_at: null,
    completed_at: null,
    first_opened_at: null,
    missed_reason: null,
    counted_toward_missed_streak: false,
    revoked_at: null,
    revoked_reason: null,
    disqualified_at: null,
    disqualified_reason: null,
    book_title: "War of the Realms",
    author_name: "Elias Thorn",
    book_route_title: "War of the Realms",
    progress_pct: 0,
    chapters_total: 12,
    chapters_read_count: 0,
    comment_count: 0,
    feedback_item_count: 0,
    question_count: 2,
    answered_question_count: 0,
    current_chapter: 1,
    status_label: "Not started",
    primary_action: "Start",
    submission_allowed: false,
    is_overdue: false,
    consecutive_missed_beta_reads: 0,
    penalty_status: "none",
    penalty_warning: null,
  },
  {
    id: "beta-3",
    book_id: "book-1",
    author_user_id: "user-1",
    reader_user_id: "reader-1",
    reader_email: "reader@example.com",
    collaborator_id: "collab-beta-3",
    state: "ready_to_submit",
    view_bucket: "active",
    task_label: "Final feedback",
    scope_kind: "full_book",
    section_label: null,
    chapter_start: null,
    chapter_end: null,
    window_days: 4,
    required_progress_pct: 100,
    required_comment_count: 3,
    required_feedback_item_count: 3,
    require_final_feedback: true,
    starts_at: "2026-05-12T12:00:00Z",
    expires_at: "2026-05-18T23:59:00Z",
    access_granted_at: "2026-05-12T12:00:00Z",
    submitted_at: null,
    completed_at: null,
    first_opened_at: "2026-05-12T13:00:00Z",
    missed_reason: null,
    counted_toward_missed_streak: false,
    revoked_at: null,
    revoked_reason: null,
    disqualified_at: null,
    disqualified_reason: null,
    book_title: "Shadows of the Past",
    author_name: "Mira Voss",
    book_route_title: "Shadows of the Past",
    progress_pct: 100,
    chapters_total: 12,
    chapters_read_count: 12,
    comment_count: 3,
    feedback_item_count: 3,
    question_count: 3,
    answered_question_count: 2,
    current_chapter: 12,
    status_label: "Ready to submit",
    primary_action: "Submit feedback",
    submission_allowed: true,
    is_overdue: false,
    consecutive_missed_beta_reads: 0,
    penalty_status: "none",
    penalty_warning: null,
  },
  {
    id: "beta-4",
    book_id: "book-1",
    author_user_id: "user-1",
    reader_user_id: "reader-1",
    reader_email: "reader@example.com",
    collaborator_id: "collab-beta-4",
    state: "active",
    view_bucket: "scheduled",
    task_label: "Review Chapter 3",
    scope_kind: "chapter_range",
    section_label: null,
    chapter_start: 3,
    chapter_end: 3,
    window_days: 4,
    required_progress_pct: 100,
    required_comment_count: 2,
    required_feedback_item_count: 2,
    require_final_feedback: true,
    starts_at: "2026-05-18T12:00:00Z",
    expires_at: "2026-05-22T23:59:00Z",
    access_granted_at: "2026-05-14T10:00:00Z",
    submitted_at: null,
    completed_at: null,
    first_opened_at: null,
    missed_reason: null,
    counted_toward_missed_streak: false,
    revoked_at: null,
    revoked_reason: null,
    disqualified_at: null,
    disqualified_reason: null,
    book_title: "Skyward Hollow",
    author_name: "Juniper Wren",
    book_route_title: "Skyward Hollow",
    progress_pct: 0,
    chapters_total: 1,
    chapters_read_count: 0,
    comment_count: 0,
    feedback_item_count: 0,
    question_count: 1,
    answered_question_count: 0,
    current_chapter: 3,
    status_label: "Scheduled",
    primary_action: "View",
    submission_allowed: false,
    is_overdue: false,
    consecutive_missed_beta_reads: 0,
    penalty_status: "none",
    penalty_warning: null,
  },
  {
    id: "beta-5",
    book_id: "book-1",
    author_user_id: "user-1",
    reader_user_id: "reader-1",
    reader_email: "reader@example.com",
    collaborator_id: "collab-beta-5",
    state: "completed",
    view_bucket: "completed",
    task_label: "Full manuscript beta read",
    scope_kind: "full_book",
    section_label: null,
    chapter_start: null,
    chapter_end: null,
    window_days: 3,
    required_progress_pct: 100,
    required_comment_count: 3,
    required_feedback_item_count: 3,
    require_final_feedback: true,
    starts_at: "2026-05-05T12:00:00Z",
    expires_at: "2026-05-08T23:59:00Z",
    access_granted_at: "2026-05-05T12:00:00Z",
    submitted_at: "2026-05-08T18:00:00Z",
    completed_at: "2026-05-08T18:05:00Z",
    first_opened_at: "2026-05-05T14:00:00Z",
    missed_reason: null,
    counted_toward_missed_streak: false,
    revoked_at: null,
    revoked_reason: null,
    disqualified_at: null,
    disqualified_reason: null,
    book_title: "The Glass Orchard",
    author_name: "Talia Moor",
    book_route_title: "The Glass Orchard",
    progress_pct: 100,
    chapters_total: 12,
    chapters_read_count: 12,
    comment_count: 4,
    feedback_item_count: 4,
    question_count: 2,
    answered_question_count: 2,
    current_chapter: 12,
    status_label: "Completed",
    primary_action: "View",
    submission_allowed: false,
    is_overdue: false,
    consecutive_missed_beta_reads: 0,
    penalty_status: "none",
    penalty_warning: null,
  },
  {
    id: "beta-6",
    book_id: "book-1",
    author_user_id: "user-1",
    reader_user_id: "reader-1",
    reader_email: "reader@example.com",
    collaborator_id: "collab-beta-6",
    state: "missed",
    view_bucket: "missed",
    task_label: "Act two beta read",
    scope_kind: "full_book",
    section_label: null,
    chapter_start: null,
    chapter_end: null,
    window_days: 3,
    required_progress_pct: 100,
    required_comment_count: 3,
    required_feedback_item_count: 3,
    require_final_feedback: true,
    starts_at: "2026-05-01T12:00:00Z",
    expires_at: "2026-05-04T23:59:00Z",
    access_granted_at: "2026-05-01T12:00:00Z",
    submitted_at: null,
    completed_at: null,
    first_opened_at: "2026-05-01T13:00:00Z",
    missed_reason: "deadline_expired",
    counted_toward_missed_streak: true,
    revoked_at: null,
    revoked_reason: null,
    disqualified_at: null,
    disqualified_reason: null,
    book_title: "Salt and Ember",
    author_name: "Ari Sol",
    book_route_title: "Salt and Ember",
    progress_pct: 40,
    chapters_total: 12,
    chapters_read_count: 5,
    comment_count: 1,
    feedback_item_count: 1,
    question_count: 2,
    answered_question_count: 0,
    current_chapter: 5,
    status_label: "Missed",
    primary_action: "View",
    submission_allowed: false,
    is_overdue: true,
    consecutive_missed_beta_reads: 2,
    penalty_status: "strong_warning",
    penalty_warning: "You missed 2 beta reads in a row. One more missed deadline may trigger a beta-read penalty review.",
  },
] as const

const initialBetaReadQuestions: Record<string, Array<{ id: string; prompt: string; created_at: string; answer_count: number }>> = {
  "beta-1": [
    { id: "question-1", prompt: "Did Chapter 12 hook you immediately?", created_at: "2026-05-13T12:00:00Z", answer_count: 1 },
    { id: "question-2", prompt: "Where did you get confused?", created_at: "2026-05-13T12:00:00Z", answer_count: 0 },
  ],
  "beta-2": [
    { id: "question-3", prompt: "Was the villain reveal predictable?", created_at: "2026-05-14T10:00:00Z", answer_count: 0 },
    { id: "question-4", prompt: "Which character did you care about most?", created_at: "2026-05-14T10:00:00Z", answer_count: 0 },
  ],
  "beta-3": [
    { id: "question-5", prompt: "Did Chapter 3 hook you?", created_at: "2026-05-12T12:00:00Z", answer_count: 1 },
    { id: "question-6", prompt: "Where did you get confused?", created_at: "2026-05-12T12:00:00Z", answer_count: 1 },
    { id: "question-7", prompt: "Which moment felt predictable?", created_at: "2026-05-12T12:00:00Z", answer_count: 0 },
  ],
  "beta-4": [
    { id: "question-8", prompt: "Did the opening land fast enough?", created_at: "2026-05-14T10:00:00Z", answer_count: 0 },
  ],
  "beta-5": [
    { id: "question-9", prompt: "Which emotional turn landed best?", created_at: "2026-05-05T12:00:00Z", answer_count: 1 },
    { id: "question-10", prompt: "Where would you tighten the middle?", created_at: "2026-05-05T12:00:00Z", answer_count: 1 },
  ],
  "beta-6": [
    { id: "question-11", prompt: "Where did the pacing drag?", created_at: "2026-05-01T12:00:00Z", answer_count: 0 },
    { id: "question-12", prompt: "What scene felt least clear?", created_at: "2026-05-01T12:00:00Z", answer_count: 0 },
  ],
}

const initialBetaReadFeedbackItems: Record<string, Array<{
  id: string
  kind: string
  chapter_number: number | null
  scene_id: string | null
  scene_title: string | null
  question_id: string | null
  question_prompt: string | null
  reaction: string | null
  anchor_text: string | null
  body: string | null
  created_at: string
  updated_at: string
}>> = {
  "beta-1": [
    {
      id: "feedback-1",
      kind: "chapter_comment",
      chapter_number: 12,
      scene_id: null,
      scene_title: null,
      question_id: null,
      question_prompt: null,
      reaction: null,
      anchor_text: "The coronation hallway scene",
      body: "The setup is strong, but the reveal takes one paragraph too long.",
      created_at: "2026-05-13T15:00:00Z",
      updated_at: "2026-05-13T15:00:00Z",
    },
    {
      id: "feedback-2",
      kind: "answer",
      chapter_number: 12,
      scene_id: null,
      scene_title: null,
      question_id: "question-1",
      question_prompt: "Did Chapter 12 hook you immediately?",
      reaction: null,
      anchor_text: null,
      body: "Yes, the first page lands well because the pressure is immediate.",
      created_at: "2026-05-13T15:05:00Z",
      updated_at: "2026-05-13T15:05:00Z",
    },
  ],
  "beta-2": [],
  "beta-3": [
    {
      id: "feedback-3",
      kind: "favorite",
      chapter_number: 8,
      scene_id: null,
      scene_title: null,
      question_id: null,
      question_prompt: null,
      reaction: null,
      anchor_text: "The rooftop confession",
      body: "This was the emotional high point for me.",
      created_at: "2026-05-13T12:00:00Z",
      updated_at: "2026-05-13T12:00:00Z",
    },
    {
      id: "feedback-4",
      kind: "answer",
      chapter_number: 3,
      scene_id: null,
      scene_title: null,
      question_id: "question-5",
      question_prompt: "Did Chapter 3 hook you?",
      reaction: null,
      anchor_text: null,
      body: "Yes, especially once the courier lied about the map.",
      created_at: "2026-05-13T12:10:00Z",
      updated_at: "2026-05-13T12:10:00Z",
    },
    {
      id: "feedback-5",
      kind: "confusing",
      chapter_number: 7,
      scene_id: null,
      scene_title: null,
      question_id: "question-6",
      question_prompt: "Where did you get confused?",
      reaction: null,
      anchor_text: "The archive vault handoff",
      body: "I lost track of who was carrying the key during this exchange.",
      created_at: "2026-05-13T12:20:00Z",
      updated_at: "2026-05-13T12:20:00Z",
    },
  ],
  "beta-4": [],
  "beta-5": [
    {
      id: "feedback-6",
      kind: "answer",
      chapter_number: 6,
      scene_id: null,
      scene_title: null,
      question_id: "question-9",
      question_prompt: "Which emotional turn landed best?",
      reaction: null,
      anchor_text: null,
      body: "The orchard argument was the strongest turn in the draft.",
      created_at: "2026-05-08T17:00:00Z",
      updated_at: "2026-05-08T17:00:00Z",
    },
  ],
  "beta-6": [
    {
      id: "feedback-7",
      kind: "boring",
      chapter_number: 5,
      scene_id: null,
      scene_title: null,
      question_id: null,
      question_prompt: null,
      reaction: null,
      anchor_text: "The market inventory section",
      body: "This section felt long relative to the plot movement.",
      created_at: "2026-05-02T15:00:00Z",
      updated_at: "2026-05-02T15:00:00Z",
    },
  ],
}

function computeBetaReadSummary(feedbackItems: Array<{ kind: string }>) {
  return {
    feedback_item_count: feedbackItems.length,
    chapter_comment_count: feedbackItems.filter((item) => item.kind === "chapter_comment").length,
    scene_reaction_count: feedbackItems.filter((item) => item.kind === "scene_reaction").length,
    answer_count: feedbackItems.filter((item) => item.kind === "answer").length,
    confusing_count: feedbackItems.filter((item) => item.kind === "confusing").length,
    boring_count: feedbackItems.filter((item) => item.kind === "boring").length,
    favorite_count: feedbackItems.filter((item) => item.kind === "favorite").length,
  }
}

const booksStats = {
  public: {
    total_books_read: 2,
    total_words_read: 60171,
  },
  private: {
    total_uploads: 4,
    total_token_consumption: 42000,
    total_chapters_tracked: 19,
    saved_quotes: 11,
  },
  writing: {
    today: { words: 1202, target_words: 1200, progress_pct: 100 },
    this_week: { words: 2565, target_words: 8400, progress_pct: 31 },
    this_month: { words: 23065, target_words: null, progress_pct: null },
    this_year: { words: 60171, target_words: null, progress_pct: null },
    last_24_hours: { words: 2565, target_words: null, progress_pct: null },
    last_7_days: { words: 14678, target_words: null, progress_pct: null },
    last_30_days: { words: 60171, target_words: null, progress_pct: null },
    last_year: { words: 60171, target_words: null, progress_pct: null },
    heatmap: [
      "2026-04-20",
      "2026-04-21",
      "2026-04-22",
      "2026-04-23",
      "2026-04-24",
      "2026-04-25",
      "2026-04-26",
      "2026-04-27",
      "2026-04-28",
      "2026-04-29",
      "2026-04-30",
      "2026-05-01",
      "2026-05-02",
      "2026-05-03",
      "2026-05-04",
      "2026-05-05",
      "2026-05-06",
      "2026-05-07",
      "2026-05-08",
      "2026-05-09",
      "2026-05-10",
      "2026-05-11",
      "2026-05-12",
      "2026-05-13",
      "2026-05-14",
    ].map((date, index) => ({
      date,
      words: [0, 0, 120, 240, 0, 80, 0, 0, 0, 160, 220, 310, 0, 0, 450, 610, 720, 900, 1040, 1150, 0, 430, 580, 762, 1202][index] ?? 0,
    })),
    entries_today: [
      { book_id: "book-1", chapter_number: 36, title: "Chapter XXXVI", words: 763 },
      { book_id: "book-1", chapter_number: null, title: "Epilogue", words: 439 },
    ],
  },
}

const chapterList = {
  read_upto: 2,
  current_chapter: 2,
  chapters: [
    { number: 1, title: "Ashfall", processed: true, intelligence_available: true, read: true },
    { number: 2, title: "The Ember Gate", processed: true, intelligence_available: true, read: true },
    { number: 3, title: "River of Glass", processed: false, intelligence_available: false, read: false },
  ],
}

const chapter = {
  chapter_number: 2,
  chapter_title: "The Ember Gate",
  total_chapters: 3,
  intelligence_available: true,
  text_url: null,
  text_content:
    [
      "Nora crossed the ember gate with ash on her sleeves. The city bells rang beyond the bridge.",
      "The courier behind her whispered that the old road remembered every footstep.",
      "* * *",
      "Morning came with a hard white sun and the smell of metal in the rain.",
      "RADIO: All westbound gates remain closed until the ashfall advisory is lifted.",
      "> CITY BULLETIN\n> Curfew begins at ninth bell. Keep identification papers ready.",
    ].join("\n\n"),
  html_content:
    "<p>Nora crossed the ember gate with ash on her sleeves.</p><p>The city bells rang beyond the bridge.</p><p>The courier behind her whispered that the old road remembered every footstep.</p><p>* * *</p><p>Morning came with a hard white sun and the smell of metal in the rain.</p>",
  media: [],
  characters: [
    {
      id: "char-1",
      name: "Nora Vale",
      aliases: ["Nora"],
      role: "mc",
      first_chapter: 1,
      description: "A determined courier.",
      personality_tags: ["determined", "curious"],
    },
  ],
}

const characterBibleCharacters: Character[] = [
  {
    id: "char-gregor",
    book_id: "book-1",
    name: "Gregor",
    aliases: [],
    role: "mc",
    first_chapter: 1,
    last_seen_chapter: 4,
    mention_count: 16,
    status: "alive",
    trait_state: {},
    description: "A traveling salesman struggling under family pressure.",
    personality_tags: ["dutiful", "isolated"],
    goal: "Keep supporting his family.",
    motivations: ["Protect his family"],
    fears: ["Becoming a burden"],
    archetype: null,
    arc_summary: "Gregor's self-worth erodes as his family turns from dependence to rejection.",
    relationship_summaries: ["Tense family bond with Grete."],
    arc_tracker: {
      summary: "Gregor remains emotionally tied to his family even as that bond deteriorates.",
      relationship_changes: [
        {
          counterpart_id: "char-grete",
          counterpart_name: "Grete",
          chapter_number: 3,
          type: "family",
          sentiment: 0.3,
          description: "Grete still cares for Gregor, but strain is showing.",
        },
        {
          counterpart_id: "char-grete",
          counterpart_name: "Grete",
          chapter_number: 3,
          type: "family",
          sentiment: -0.2,
          description: "Grete's patience frays as the household pressure rises.",
        },
      ],
      contradictions: [],
      diagnostics: [],
      voice_markers: ["careful", "self-effacing"],
    },
  },
  {
    id: "char-grete",
    book_id: "book-1",
    name: "Grete",
    aliases: [],
    role: "sc",
    first_chapter: 1,
    last_seen_chapter: 4,
    mention_count: 12,
    status: "alive",
    trait_state: {},
    description: "Gregor's sister, pulled between duty and resentment.",
    personality_tags: ["dutiful", "frustrated"],
    goal: "Hold the family together.",
    motivations: ["Keep order at home"],
    fears: ["Losing her future"],
    archetype: null,
    arc_summary: "Grete shifts from caretaker to the family member who sets a final boundary.",
    relationship_summaries: ["Caretaker bond with Gregor."],
  },
  {
    id: "char-gregors-sister",
    book_id: "book-1",
    name: "Gregor's sister",
    aliases: [],
    role: "background",
    first_chapter: 2,
    last_seen_chapter: 4,
    mention_count: 7,
    status: "alive",
    trait_state: {},
    description: "A duplicate-style family-role label that should be manually mergeable.",
    personality_tags: ["resentful"],
    goal: "Escape the family's pressure.",
    motivations: ["Find independence"],
    fears: ["Being trapped at home"],
    archetype: null,
    arc_summary: "This card exists so duplicate review can be exercised in browser tests.",
    relationship_summaries: ["Likely overlaps with Grete."],
  },
  {
    id: "char-mr-samsa",
    book_id: "book-1",
    name: "Mr. Samsa",
    aliases: ["Gregor's father"],
    role: "background",
    first_chapter: 1,
    last_seen_chapter: 4,
    mention_count: 9,
    status: "alive",
    trait_state: {},
    description: "Gregor's father, rigid and volatile under financial strain.",
    personality_tags: ["defensive", "proud"],
    goal: "Restore control over the household.",
    motivations: ["Protect family order"],
    fears: ["Financial collapse"],
    archetype: null,
    arc_summary: "Mr. Samsa hardens as the family reorients around survival.",
    relationship_summaries: ["Conflict with Gregor."],
  },
]

const relationshipGraph = {
  nodes: characterBibleCharacters.map((character) => ({
    id: character.id,
    name: character.name,
    role: character.role,
    first_chapter: character.first_chapter,
    description: character.description,
    personality_tags: character.personality_tags,
    aliases: character.aliases,
    motivations: character.motivations,
    fears: character.fears,
    archetype: character.archetype,
    arc_summary: character.arc_summary,
  })),
  edges: [
    {
      id: "edge-gregor-grete-1",
      source: "char-gregor",
      target: "char-grete",
      type: "family",
      sentiment: 1,
      description: "Sibling bond under pressure.",
      from_chapter: 1,
      to_chapter: 4,
    },
    {
      id: "edge-gregor-mr-samsa-1",
      source: "char-gregor",
      target: "char-mr-samsa",
      type: "family",
      sentiment: -1,
      description: "A strained father-son relationship.",
      from_chapter: 1,
      to_chapter: 4,
    },
  ],
}

const chaptersByNumber = {
  1: {
    chapter_number: 1,
    chapter_title: "Ashfall",
    total_chapters: 3,
    intelligence_available: true,
    text_url: null,
    text_content:
      "Nora leaves the outer district with a sealed message and no time to second-guess the mission.",
    html_content:
      "<p>Nora leaves the outer district with a sealed message and no time to second-guess the mission.</p>",
    media: [],
    characters: chapter.characters,
  },
  2: chapter,
  3: {
    chapter_number: 3,
    chapter_title: "River of Glass",
    total_chapters: 3,
    intelligence_available: false,
    text_url: null,
    text_content: "",
    html_content: "<p></p>",
    media: [],
    characters: chapter.characters,
  },
} as const

const storyHealth = {
  score: 82,
  status: "Stable",
  summary: "Character arcs and plot continuity are holding together in the current draft.",
  metrics: [
    { label: "Characters", score: 88 },
    { label: "World Coherence", score: 80 },
    { label: "Plot Consistency", score: 79 },
    { label: "Pacing", score: 76 },
  ],
}

const writerWorkspace = {
  word_count_goals: {
    chapter_target: 2500,
    book_target: 90000,
    session_target: 800,
  },
  goal_calendar: [],
  corkboard_cards: [],
  templates: [
    {
      id: "template-1",
      kind: "scene",
      title: "Scene Starter",
      description: "A quick outline for a new scene.",
      content: "Goal:\nConflict:\nTurn:",
    },
  ],
  publishing: {
    active_preset: "standard_manuscript",
    trim_size: "6x9",
    include_title_page: true,
    mirror_margins: false,
  },
  manuscript_front_matter: {
    author_name: "M. Vale",
    pen_name: "",
    contact_email: "author@getlorevia.com",
    contact_phone: "",
    contact_address: "",
    title: "Sky of Ash",
    subtitle: "",
    header_last_name: "Vale",
    header_title: "Sky of Ash",
    approximate_word_count_override: null,
    dedication: "",
    acknowledgments: "",
    epigraph: "",
    prologue: "",
    include_dedication: false,
    include_acknowledgments: false,
    include_epigraph: false,
    include_prologue: false,
  },
  revision_board: {
    items: [],
    last_generated_at: null,
  },
  processing: book.processing,
}

const revisionIntelligence = {
  tagline: "Know what your edit breaks before your readers do.",
  summary: {
    hero_message: "2 downstream logic risks need attention first.",
    active_item_count: 5,
    high_severity_count: 2,
    task_ready_count: 5,
    recent_edit_label: "You changed Chapter 2: removed or weakened silver gate, blood.",
  },
  change_impacts: [
    {
      id: "rev-impact-1",
      category: "impact",
      title: "Chapter 2 assumption may break later payoff",
      description: "Chapter 3 still assumes Nora and Kael already understand the silver gate blood rule.",
      severity: "high",
      chapter_ref: 2,
      source_label: "The Ember Gate",
      recommendation: "Restore the setup or revise the later dialogue so the reveal still tracks.",
      status: "pending",
      assigned_version_id: null,
      task_id: null,
    },
  ],
  genre_checks: [
    {
      genre: "epic fantasy",
      label: "Fantasy",
      checks: ["magic system consistency", "faction politics", "invented terms", "worldbuilding contradictions"],
      rationale: "LoreVia is weighting revision checks toward the story promises and failure modes that usually matter most in fantasy manuscripts.",
    },
  ],
  revision_plan: [
    {
      title: "Pass 1: Fix story logic",
      summary: "Resolve the items most likely to create downstream contradictions or broken assumptions.",
      items: [
        {
          id: "rev-impact-1",
          category: "impact",
          title: "Chapter 2 assumption may break later payoff",
          description: "Chapter 3 still assumes Nora and Kael already understand the silver gate blood rule.",
          severity: "high",
          chapter_ref: 2,
          status: "pending",
          assigned_version_id: null,
          task_id: null,
        },
      ],
    },
  ],
  knowledge_matrix: [
    {
      fact: "Silver gate blood rule",
      chapter_ref: 2,
      entries: [
        { character_name: "Nora", chapter_learned: 2, source: "Tracked through the silver gate thread" },
        { character_name: "Kael", chapter_learned: 2, source: "Tracked through the silver gate thread" },
        { character_name: "Mira", chapter_learned: null, source: "No earlier evidence surfaced yet" },
      ],
      warning: "LoreVia has no clear evidence yet that Mira learned this before later story beats could depend on it.",
    },
  ],
  knowledge_timeline: [
    {
      fact: "Silver gate blood rule",
      rows: [
        {
          character_name: "Nora",
          chapter_learned: 2,
          source: "Tracked through the silver gate thread",
          cells: [
            { chapter_number: 1, state: "unknown" },
            { chapter_number: 2, state: "learned" },
            { chapter_number: 3, state: "known" },
          ],
        },
        {
          character_name: "Kael",
          chapter_learned: 2,
          source: "Tracked through the silver gate thread",
          cells: [
            { chapter_number: 1, state: "unknown" },
            { chapter_number: 2, state: "learned" },
            { chapter_number: 3, state: "known" },
          ],
        },
        {
          character_name: "Mira",
          chapter_learned: null,
          source: "No earlier evidence surfaced yet",
          cells: [
            { chapter_number: 1, state: "unknown" },
            { chapter_number: 2, state: "unknown" },
            { chapter_number: 3, state: "unknown" },
          ],
        },
      ],
      warning: "LoreVia has no clear evidence yet that Mira learned this before later story beats could depend on it.",
    },
  ],
  scene_advice: [
    {
      id: "rev-scene-1",
      category: "scene",
      title: "Scenes in Chapters 2 and 3 may be doing duplicate work",
      description: "Both scenes repeat the gate warning and delay the same reveal beat.",
      severity: "medium",
      chapter_ref: 3,
      status: "pending",
      assigned_version_id: null,
      task_id: null,
    },
  ],
  confusion_map: [
    {
      id: "rev-confusion-1",
      category: "confusion",
      title: "Reader confusion risk in Chapter 1",
      description: "4 named characters arrive here; 3 lore terms appear here.",
      severity: "medium",
      chapter_ref: 1,
      status: "pending",
      assigned_version_id: null,
      task_id: null,
    },
  ],
  voice_alerts: [
    {
      id: "rev-voice-1",
      category: "voice",
      title: "Nora's voice drifts in Chapter 3",
      description: "The dialogue turns unusually formal and exposition-heavy for Nora's baseline.",
      severity: "medium",
      chapter_ref: 3,
      status: "pending",
      assigned_version_id: null,
      task_id: null,
    },
  ],
}

const workspaceTree = {
  chapters: [
    { chapter_number: 1, title: "Ashfall", scene_count: 1, structure_version: 0 },
    { chapter_number: 2, title: "The Ember Gate", scene_count: 2, structure_version: 4 },
  ],
  scene_groups: [
    {
      id: "chapter-scenes-2",
      label: "Chapter 2: The Ember Gate",
      chapter_number: 2,
      structure_version: 4,
      collapsed_by_default: false,
      scenes: [
        {
          id: "scene-1",
          book_id: "book-1",
          chapter_id: null,
          chapter_number: 2,
          title: "Gate Crossing",
          description: "Nora reaches the city gate.",
          body: "Nora crosses into the city.",
          html_body: "<p>Nora crosses into the city.</p>",
          metadata: {},
          path: "Scenes/Chapter 2/Gate Crossing.md",
          status: "assigned",
          sort_order: 1,
          source: "manual",
          origin_chapter_number: 2,
          created_at: "2026-05-08T10:00:00Z",
          updated_at: "2026-05-08T10:10:00Z",
        },
        {
          id: "scene-2",
          book_id: "book-1",
          chapter_id: null,
          chapter_number: 2,
          title: "Market Argument",
          description: "Nora and Kael clash in the square.",
          body: "The market square erupted around them.",
          html_body: "<p>The market square erupted around them.</p>",
          metadata: {},
          path: "Scenes/Chapter 2/Market Argument.md",
          status: "assigned",
          sort_order: 2,
          source: "manual",
          origin_chapter_number: 2,
          created_at: "2026-05-08T10:15:00Z",
          updated_at: "2026-05-08T10:20:00Z",
        },
      ],
    },
  ],
  note_paths: ["Notes/Chapter 2/Bridge notes.md"],
}

const preWritingCheck = {
  upcoming_chapter: 3,
  active_characters: [
    {
      character_id: "char-1",
      character_name: "Nora Vale",
      role: "mc",
      active_goal: "Reach the archive before dawn.",
    },
  ],
  unresolved_threads: [
    {
      id: "thread-1",
      title: "Who opened the gate?",
      status: "open",
      last_updated_chapter: 2,
      note: "Still unresolved after the bridge sequence.",
    },
  ],
  recent_events: [
    {
      chapter_number: 2,
      chapter_title: "The Ember Gate",
      summary: "Nora enters the city and hears the bells.",
    },
  ],
  alerts: [],
}

const emotionalArc = {
  focus_character_count: 1,
  latest_turning_points: ["Nora commits to reaching the archive."],
  characters: [
    {
      character_id: "char-1",
      character_name: "Nora Vale",
      role: "mc",
      arc_summary: "Nora is leaning into responsibility.",
      trajectory_score: 0.78,
      points: [
        {
          chapter_number: 1,
          label: "Departure",
          sentiment: 0.2,
          impact_score: 0.5,
          growth_direction: "up",
        },
      ],
    },
  ],
}

const synopsis = {
  spoiler_level: "minimal",
  synopsis:
    "Nora is carrying dangerous knowledge into the city while the political stakes around the ember gate continue rising.",
  focus_points: ["Nora's mission", "The ember gate", "Unresolved political tension"],
  coverage_chapters: [1, 2],
}

const notifications = {
  items: [
    {
      id: "notification-revision-1",
      book_id: "book-1",
      kind: "revision_digest",
      title: "2 revision risks surfaced in Sky of Ash",
      body: "2 downstream logic risks need attention first. Top issue: Chapter 2 assumption may break later payoff.",
      data: {
        tagline: "Know what your edit breaks before your readers do.",
        hero_message: "2 downstream logic risks need attention first.",
        active_item_count: 5,
        high_severity_count: 2,
        task_ready_count: 5,
        recent_edit_label: "You changed Chapter 2: removed or weakened silver gate, blood.",
        top_item_title: "Chapter 2 assumption may break later payoff",
      },
      read_at: null,
      created_at: "2026-05-11T11:00:00Z",
    },
  ],
  unread_count: 1,
}

const notes = [
  {
    id: "note-1",
    book_id: "book-1",
    book_title: "Sky of Ash",
    chapter_number: 2,
    chapter_title: "The Ember Gate",
    title: "Gate imagery",
    body: "Revisit the bell motif.",
    created_at: "2026-05-08T10:00:00Z",
    updated_at: "2026-05-08T10:00:00Z",
  },
]

const manuscriptAnnotations = [
  {
    id: "annotation-1",
    book_id: "book-1",
    book_title: "Sky of Ash",
    chapter_number: 2,
    chapter_title: "The Ember Gate",
    category: "continuity",
    status: "open",
    visibility: "shared",
    quote: "The courier behind her whispered that the old road remembered every footstep.",
    comment: "Keep the road language consistent with the later bridge beat.",
    anchor_context_before: "The city bells rang beyond the bridge.",
    anchor_context_after: "The gate answered with a low ember hum.",
    start_offset: 0,
    end_offset: 70,
    created_by_user_id: "user-1",
    created_by_label: "Madhav",
    can_edit: true,
    resolved_at: null,
    created_at: "2026-05-08T10:00:00Z",
    updated_at: "2026-05-08T10:00:00Z",
  },
]

const collaborators = [
  {
    id: "collab-1",
    book_id: "book-1",
    email: "beta@example.com",
    display_name: "Beta Reader",
    role: "beta_reader",
    scope: {
      chapter_start: 1,
      chapter_end: 10,
      character_bible: true,
      continuity_report: true,
      reader_confusion_report: true,
    },
    permissions: {
      can_edit_manuscript: false,
      can_view_story_bible: true,
      can_run_ai_scans: true,
      can_export: false,
      can_comment: true,
      can_view_selected_chapters_only: true,
    },
    invite_status: "active",
    invited_at: "2026-05-08T10:00:00Z",
    updated_at: "2026-05-08T10:00:00Z",
  },
]

const worldBuildingDocuments = [
  {
    id: "world-doc-1",
    book_id: "book-1",
    title: "Core World Notes",
    source_name: "core-world-notes.txt",
    word_count: 186,
    is_active: true,
    archived_at: null,
    created_at: "2026-05-08T10:00:00Z",
    updated_at: "2026-05-08T11:00:00Z",
  },
]

const worldBuildingDocumentDetail = {
  ...worldBuildingDocuments[0],
  text: "Northreach is a desert capital. Glass Road is the main trade route. Salt Marks are used for tolls.",
  html: null,
}

const worldElements = [
  {
    id: "world-element-1",
    book_id: "book-1",
    series_id: null,
    world_document_id: "world-doc-1",
    source_scope: "worldbuilding",
    element_type: "place",
    name: "Northreach",
    description: "Northreach is a desert capital with a thin canon note that still needs stronger grounding.",
    parent_element_id: null,
    dependencies: [],
    usage_count: 3,
    gap_score: 0.62,
    integration_score: 0.51,
    suggestions: [],
    edited_by_author: false,
    is_series_canonical: false,
    created_at: "2026-05-08T10:00:00Z",
    updated_at: "2026-05-08T11:00:00Z",
    chapter_number: 2,
    chapter_title: "The Ember Gate",
    world_document_title: "Core World Notes",
    canonical_name: "Northreach",
    aliases: [],
    confidence: 0.88,
    provenance: [],
    claims: [],
    chapter_numbers: [2],
    chapter_count: 1,
    summary_mentions: 1,
    presence_score: 0.54,
    narrative_modes: ["worldbuilding_note"],
    source_excerpt: "Northreach is a desert capital.",
    character_id: null,
    author_override: false,
  },
]

const worldGapAnalysis = {
  mode: "gap_detection",
  generated_at: "2026-05-13T11:30:00Z",
  gap_categories: {
    coverage_watchlist: [
      {
        id: "coverage-watch-northreach-note",
        category: "coverage_watchlist",
        severity: "low",
        title: "Northreach needs a clearer canon note",
        description: "This lore is present in the active world corpus, but the canon detail is still thin for continuity checks and later retrieval.",
        suggested_fix: "Expand Northreach with stable facts, limits, relationships, and consequences so later chapters can reuse the same canon cleanly.",
        world_evidence: "Northreach is a desert capital.",
        story_evidence: "Nora crosses toward the city bells beyond the bridge.",
        world_document_id: "world-doc-1",
        world_document_title: "Core World Notes",
        story_chapter_number: 2,
        story_chapter_title: "The Ember Gate",
        character_name: null,
        priority: 4,
        entity_type: "place",
        canonical_name: "Northreach",
        confidence: 0.88,
        provenance: { world: [], story: [] },
      },
      {
        id: "coverage-watch-glass-road-anchor",
        category: "coverage_watchlist",
        severity: "low",
        title: "Glass Road needs one more story anchor",
        description: "The canon exists, but the manuscript still gives readers only light runway for this world element.",
        suggested_fix: "Reinforce Glass Road in one earlier scene, summary beat, or dialogue exchange so readers can track it before later payoff.",
        world_evidence: "Glass Road is the main trade route.",
        story_evidence: "The courier behind Nora whispers that the old road remembers every footstep.",
        world_document_id: "world-doc-1",
        world_document_title: "Core World Notes",
        story_chapter_number: 2,
        story_chapter_title: "The Ember Gate",
        character_name: null,
        priority: 4,
        entity_type: "travel_rule",
        canonical_name: "Glass Road",
        confidence: 0.73,
        provenance: { world: [], story: [] },
      },
    ],
  },
  gap_groups: [
    {
      key: "coverage_watchlist",
      label: "Coverage watchlist",
      description: "LoreVia keeps a short queue of under-specified canon areas so there are always concrete worldbuilding review targets to tighten.",
      items: [
        {
          id: "coverage-watch-northreach-note",
          category: "coverage_watchlist",
          severity: "low",
          title: "Northreach needs a clearer canon note",
          description: "This lore is present in the active world corpus, but the canon detail is still thin for continuity checks and later retrieval.",
          suggested_fix: "Expand Northreach with stable facts, limits, relationships, and consequences so later chapters can reuse the same canon cleanly.",
          world_evidence: "Northreach is a desert capital.",
          story_evidence: "Nora crosses toward the city bells beyond the bridge.",
          world_document_id: "world-doc-1",
          world_document_title: "Core World Notes",
          story_chapter_number: 2,
          story_chapter_title: "The Ember Gate",
          character_name: null,
          priority: 4,
          entity_type: "place",
          canonical_name: "Northreach",
          confidence: 0.88,
          provenance: { world: [], story: [] },
        },
        {
          id: "coverage-watch-glass-road-anchor",
          category: "coverage_watchlist",
          severity: "low",
          title: "Glass Road needs one more story anchor",
          description: "The canon exists, but the manuscript still gives readers only light runway for this world element.",
          suggested_fix: "Reinforce Glass Road in one earlier scene, summary beat, or dialogue exchange so readers can track it before later payoff.",
          world_evidence: "Glass Road is the main trade route.",
          story_evidence: "The courier behind Nora whispers that the old road remembers every footstep.",
          world_document_id: "world-doc-1",
          world_document_title: "Core World Notes",
          story_chapter_number: 2,
          story_chapter_title: "The Ember Gate",
          character_name: null,
          priority: 4,
          entity_type: "travel_rule",
          canonical_name: "Glass Road",
          confidence: 0.73,
          provenance: { world: [], story: [] },
        },
      ],
    },
  ],
  priority_gaps: [
    {
      id: "coverage-watch-northreach-note",
      category: "coverage_watchlist",
      severity: "low",
      title: "Northreach needs a clearer canon note",
      description: "This lore is present in the active world corpus, but the canon detail is still thin for continuity checks and later retrieval.",
      suggested_fix: "Expand Northreach with stable facts, limits, relationships, and consequences so later chapters can reuse the same canon cleanly.",
      world_evidence: "Northreach is a desert capital.",
      story_evidence: "Nora crosses toward the city bells beyond the bridge.",
      world_document_id: "world-doc-1",
      world_document_title: "Core World Notes",
      story_chapter_number: 2,
      story_chapter_title: "The Ember Gate",
      character_name: null,
      priority: 4,
      entity_type: "place",
      canonical_name: "Northreach",
      confidence: 0.88,
      provenance: { world: [], story: [] },
    },
  ],
  consistency_flags: [
    {
      id: "conflict-northreach",
      type: "definition_conflict",
      title: "Conflicting definition for Northreach",
      description: "Multiple extracted descriptions disagree about this world element.",
    },
  ],
  world_elements: worldElements,
  world_documents: worldBuildingDocuments,
}

const voiceConsistency = {
  review: {
    overall_verdict: "Nora's baseline mostly holds, but one line slides into exposition-heavy narration.",
    issues: [
      {
        character_name: "Nora Vale",
        severity: "moderate",
        title: "Nora sounds more formal than her baseline",
        description: "One paragraph shifts from Nora's clipped voice into explanatory narration that reads unlike her usual cadence.",
        evidence: "The city bells rang beyond the bridge while she mentally catalogued the economic implications of every gate closure.",
        suggestion: "Trim the analytical phrasing and return to Nora's more immediate sensory language.",
        intentionality_prompt: "If this shift is intentional, add a stronger cue that Nora is deliberately narrating rather than reacting in-scene.",
      },
    ],
  },
  retrieved_passages: [],
  characters_reviewed: ["Nora Vale"],
  character_matches: [
    {
      character_name: "Nora Vale",
      match_score: 66,
      baseline_sample_size: 6,
      sample_dialogue_count: 3,
      strongest_signals: ["more formal phrasing", "heavier exposition"],
      closest_other_character: "Kael",
      closest_other_score: 44,
    },
  ],
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  })
}

function notFound(route: Route) {
  return json(route, { detail: "Not found" }, 404)
}

export async function installMockApi(page: Page, options: MockOptions = {}) {
  const session = options.session ?? "authenticated"
  const login = options.login ?? "success"
  let mockWriterWorkspace = JSON.parse(JSON.stringify(writerWorkspace))
  let mockNotifications = JSON.parse(JSON.stringify(notifications))
  let mockWorkspaceTree = JSON.parse(JSON.stringify(workspaceTree))
  let mockBetaReads = JSON.parse(JSON.stringify(initialBetaReads))
  let mockBetaReadQuestions = JSON.parse(JSON.stringify(initialBetaReadQuestions))
  let mockBetaReadFeedbackItems = JSON.parse(JSON.stringify(initialBetaReadFeedbackItems))
  let mockNotes = JSON.parse(JSON.stringify(notes))
  let mockManuscriptAnnotations = JSON.parse(JSON.stringify(manuscriptAnnotations))

  const buildBetaReadDetail = (assignmentId: string) => {
    const assignment = mockBetaReads.find((item: typeof mockBetaReads[number]) => item.id === assignmentId)
    if (!assignment) return null
    const authorQuestions = mockBetaReadQuestions[assignmentId] ?? []
    const feedbackItems = mockBetaReadFeedbackItems[assignmentId] ?? []
    return {
      assignment: {
        ...assignment,
        feedback_item_count: feedbackItems.length,
        question_count: authorQuestions.length,
        answered_question_count: feedbackItems.filter((item: { kind: string }) => item.kind === "answer").length,
      },
      author_questions: authorQuestions,
      feedback_items: feedbackItems,
      feedback_summary: computeBetaReadSummary(feedbackItems),
    }
  }

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())
    const path = normalizeMockApiPath(url.pathname)
    const method = route.request().method()

    if (path === "/api/v1/auth/me" && method === "GET") {
      return session === "authenticated" ? json(route, user) : json(route, { detail: "Unauthorized" }, 401)
    }

    if (path === "/api/v1/auth/refresh" && method === "POST") {
      return session === "authenticated" ? json(route, user) : json(route, { detail: "Unauthorized" }, 401)
    }

    if (path === "/api/v1/auth/login" && method === "POST") {
      return login === "success" ? json(route, user) : json(route, { detail: "Invalid credentials" }, 401)
    }

    if (path === "/api/v1/auth/logout" && method === "POST") {
      return json(route, { ok: true })
    }

    if (path === "/api/v1/notifications" && method === "GET") {
      return json(route, mockNotifications)
    }

    if (path === "/api/v1/notifications/read-all" && method === "PUT") {
      mockNotifications = {
        ...mockNotifications,
        unread_count: 0,
        items: mockNotifications.items.map((item: typeof mockNotifications.items[number]) => ({
          ...item,
          read_at: item.read_at ?? "2026-05-11T12:00:00Z",
        })),
      }
      return json(route, mockNotifications)
    }

    const notificationMatch = path.match(/^\/api\/v1\/notifications\/([^/]+)\/read$/)
    if (notificationMatch && method === "PUT") {
      const notificationId = notificationMatch[1]
      mockNotifications = {
        ...mockNotifications,
        items: mockNotifications.items.map((item: typeof mockNotifications.items[number]) =>
          item.id === notificationId ? { ...item, read_at: item.read_at ?? "2026-05-11T12:00:00Z" } : item
        ),
      }
      mockNotifications.unread_count = mockNotifications.items.filter((item: typeof mockNotifications.items[number]) => !item.read_at).length
      const updated = mockNotifications.items.find((item: typeof mockNotifications.items[number]) => item.id === notificationId)
      return updated ? json(route, updated) : notFound(route)
    }

    if (path === "/api/v1/books" && method === "GET") {
      return json(route, [book])
    }

    if (path === "/api/v1/books/stats" && method === "GET") {
      return json(route, booksStats)
    }

    if (path === "/api/v1/books/book-1" && method === "GET") {
      return json(route, book)
    }

    if (path === "/api/v1/books/book-1/collaborators" && method === "GET") {
      return json(route, collaborators)
    }

    if (path === "/api/v1/books/book-1/collaborators" && method === "POST") {
      const payload = JSON.parse(route.request().postData() || "{}")
      return json(route, {
        id: "collab-2",
        book_id: "book-1",
        email: payload.email,
        display_name: payload.display_name,
        role: payload.role,
        scope: payload.scope,
        permissions: payload.permissions,
        invite_status: "active",
        invited_at: "2026-05-11T10:00:00Z",
        updated_at: "2026-05-11T10:00:00Z",
      }, 201)
    }

    if (path === "/api/v1/books/book-1/beta-reads" && method === "GET") {
      return json(route, { items: mockBetaReads })
    }

    if (path === "/api/v1/books/book-1/beta-reads" && method === "POST") {
      const payload = route.request().postDataJSON() as Record<string, unknown>
      const created = {
        id: `beta-${mockBetaReads.length + 1}`,
        book_id: "book-1",
        author_user_id: "user-1",
        reader_user_id: "reader-1",
        reader_email: String(payload.reader_email || "reader@example.com"),
        collaborator_id: `collab-beta-${mockBetaReads.length + 1}`,
        state: "active",
        view_bucket: "active",
        task_label: String(payload.task_label || "Full manuscript beta read"),
        scope_kind: String(payload.scope_kind || "full_book"),
        section_label: payload.section_label ?? null,
        chapter_start: payload.chapter_start ?? null,
        chapter_end: payload.chapter_end ?? null,
        window_days: Number(payload.window_days || 3),
        required_progress_pct: Number(payload.required_progress_pct || 100),
        required_comment_count: Number(payload.required_comment_count || 0),
        required_feedback_item_count: Number(payload.required_feedback_item_count || 1),
        require_final_feedback: Boolean(payload.require_final_feedback ?? true),
        starts_at: String(payload.starts_at || "2026-05-14T12:00:00Z"),
        expires_at: "2026-05-17T23:59:00Z",
        access_granted_at: "2026-05-14T12:00:00Z",
        submitted_at: null,
        completed_at: null,
        first_opened_at: null,
        missed_reason: null,
        counted_toward_missed_streak: false,
        revoked_at: null,
        revoked_reason: null,
        disqualified_at: null,
        disqualified_reason: null,
        book_title: "Sky of Ash",
        author_name: "M. Vale",
        book_route_title: "Sky of Ash",
        progress_pct: 0,
        chapters_total: 12,
        chapters_read_count: 0,
        comment_count: 0,
        feedback_item_count: 0,
        question_count: Array.isArray(payload.author_questions) ? payload.author_questions.length : 0,
        answered_question_count: 0,
        current_chapter: Number(payload.chapter_start || 1),
        status_label: "Not started",
        primary_action: "Start",
        submission_allowed: false,
        is_overdue: false,
        consecutive_missed_beta_reads: 0,
        penalty_status: "none",
        penalty_warning: null,
      }
      mockBetaReads = [created, ...mockBetaReads]
      mockBetaReadQuestions[created.id] = Array.isArray(payload.author_questions)
        ? payload.author_questions
            .map((question, index) => String(question || "").trim())
            .filter(Boolean)
            .map((prompt, index) => ({
              id: `${created.id}-question-${index + 1}`,
              prompt,
              created_at: "2026-05-14T12:00:00Z",
              answer_count: 0,
            }))
        : []
      mockBetaReadFeedbackItems[created.id] = []
      return json(route, created, 201)
    }

    if (path === "/api/v1/books/book-1/characters" && method === "GET") {
      return json(route, characterBibleCharacters)
    }

    if (path === "/api/v1/books/book-1/characters" && method === "POST") {
      const payload = route.request().postDataJSON() as {
        name?: string
        first_chapter?: number
        aliases?: string[]
        role?: "mc" | "sc" | "background" | null
        description?: string | null
        goal?: string | null
        motivations?: string[]
        fears?: string[]
        lie_they_believe?: string | null
        backstory_wound?: string | null
        arc_type?: string | null
        arc_summary?: string | null
        personality_tags?: string[]
      } | null
      const created: Character = {
        id: `char-manual-${characterBibleCharacters.length + 1}`,
        book_id: "book-1",
        name: payload?.name ?? "Manual Character",
        aliases: payload?.aliases ?? [],
        role: payload?.role ?? null,
        first_chapter: payload?.first_chapter ?? 1,
        last_seen_chapter: payload?.first_chapter ?? 1,
        mention_count: 1,
        status: "alive",
        trait_state: {},
        description: payload?.description ?? null,
        personality_tags: payload?.personality_tags ?? [],
        goal: payload?.goal ?? null,
        motivations: payload?.motivations ?? [],
        fears: payload?.fears ?? [],
        lie_they_believe: payload?.lie_they_believe ?? null,
        backstory_wound: payload?.backstory_wound ?? null,
        arc_type: payload?.arc_type ?? null,
        archetype: null,
        arc_summary: payload?.arc_summary ?? null,
        relationship_summaries: [],
      }
      characterBibleCharacters.push(created)
      return json(route, created, 201)
    }

    if (path === "/api/v1/books/book-1/chapter-reports" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/books/book-1/pre-writing-check" && method === "GET") {
      return json(route, preWritingCheck)
    }

    if (path === "/api/v1/books/book-1/story-health" && method === "GET") {
      return json(route, storyHealth)
    }

    if (path === "/api/v1/books/book-1/writer-workspace" && method === "GET") {
      return json(route, mockWriterWorkspace)
    }

    if (path === "/api/v1/books/book-1/writer-workspace" && method === "PUT") {
      const body = route.request().postDataJSON() as Record<string, unknown> | null
      mockWriterWorkspace = {
        ...mockWriterWorkspace,
        ...(body ?? {}),
      }
      return json(route, mockWriterWorkspace)
    }

    if (path === "/api/v1/books/book-1/emotional-arc" && method === "GET") {
      return json(route, emotionalArc)
    }

    if (path === "/api/v1/books/book-1/revision-intelligence" && method === "GET") {
      return json(route, revisionIntelligence)
    }

    if (path === "/api/v1/books/book-1/workspace/tree" && method === "GET") {
      return json(route, mockWorkspaceTree)
    }

    const sceneOrderMatch = path.match(/^\/api\/v1\/books\/book-1\/chapters\/(\d+)\/scenes\/order$/)
    if (sceneOrderMatch && method === "PATCH") {
      const chapterNumber = Number.parseInt(sceneOrderMatch[1] ?? "", 10)
      const body = route.request().postDataJSON() as {
        scene_ids?: string[]
        expected_structure_version?: number
      } | null
      const sceneIds = body?.scene_ids ?? []
      const chapter = mockWorkspaceTree.chapters.find((item: typeof mockWorkspaceTree.chapters[number]) => item.chapter_number === chapterNumber)
      const group = mockWorkspaceTree.scene_groups.find((item: typeof mockWorkspaceTree.scene_groups[number]) => item.chapter_number === chapterNumber)

      if (!chapter || !group) {
        return notFound(route)
      }
      if ((body?.expected_structure_version ?? -1) !== chapter.structure_version) {
        return json(route, { detail: "Scene order changed elsewhere. Please refresh." }, 409)
      }

      const scenesById = new Map(group.scenes.map((scene: typeof group.scenes[number]) => [scene.id, scene]))
      const reorderedScenes = sceneIds
        .map((sceneId) => scenesById.get(sceneId))
        .filter((scene): scene is typeof group.scenes[number] => Boolean(scene))
        .map((scene, index) => ({
          ...scene,
          sort_order: index + 1,
        }))

      chapter.structure_version += 1
      group.structure_version = chapter.structure_version
      group.scenes = reorderedScenes

      return json(route, {
        chapter_number: chapterNumber,
        structure_version: chapter.structure_version,
        scenes: reorderedScenes.map((scene) => ({
          id: scene.id,
          title: scene.title,
          sort_order: scene.sort_order,
        })),
      })
    }

    if (path === "/api/v1/books/book-1/chapter-versions" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/books/book-1/annotations" && method === "GET") {
      const chapterNumber = route.request().url().includes("chapter_number=")
        ? Number.parseInt(new URL(route.request().url()).searchParams.get("chapter_number") ?? "", 10)
        : null
      const items = Number.isFinite(chapterNumber ?? Number.NaN)
        ? mockManuscriptAnnotations.filter((annotation: typeof mockManuscriptAnnotations[number]) => annotation.chapter_number === chapterNumber)
        : mockManuscriptAnnotations
      return json(route, items)
    }

    if (path === "/api/v1/books/book-1/annotations" && method === "POST") {
      const body = route.request().postDataJSON() as {
        annotation_id?: string
        chapter_number?: number
        category?: string
        status?: string
        visibility?: string
        quote?: string
        comment?: string
        anchor_context_before?: string | null
        anchor_context_after?: string | null
        start_offset?: number | null
        end_offset?: number | null
      } | null

      const existingIndex = mockManuscriptAnnotations.findIndex((annotation: typeof mockManuscriptAnnotations[number]) => annotation.id === body?.annotation_id)
      if (existingIndex >= 0) {
        const current = mockManuscriptAnnotations[existingIndex]
        const next = {
          ...current,
          category: body?.category ?? current.category,
          status: body?.status ?? current.status,
          visibility: body?.visibility ?? current.visibility,
          quote: body?.quote ?? current.quote,
          comment: body?.comment ?? current.comment,
          anchor_context_before: body?.anchor_context_before ?? current.anchor_context_before,
          anchor_context_after: body?.anchor_context_after ?? current.anchor_context_after,
          start_offset: body?.start_offset ?? current.start_offset,
          end_offset: body?.end_offset ?? current.end_offset,
          resolved_at: (body?.status ?? current.status) === "resolved" ? "2026-05-14T09:00:00Z" : null,
          updated_at: "2026-05-14T09:00:00Z",
        }
        mockManuscriptAnnotations[existingIndex] = next
        return json(route, next)
      }

      const created = {
        id: `annotation-${mockManuscriptAnnotations.length + 1}`,
        book_id: "book-1",
        book_title: "Sky of Ash",
        chapter_number: body?.chapter_number ?? 2,
        chapter_title: "The Ember Gate",
        category: body?.category ?? "general",
        status: body?.status ?? "open",
        visibility: body?.visibility ?? "shared",
        quote: body?.quote ?? "Selected passage",
        comment: body?.comment ?? "",
        anchor_context_before: body?.anchor_context_before ?? null,
        anchor_context_after: body?.anchor_context_after ?? null,
        start_offset: body?.start_offset ?? null,
        end_offset: body?.end_offset ?? null,
        created_by_user_id: "user-1",
        created_by_label: "Madhav",
        can_edit: true,
        resolved_at: body?.status === "resolved" ? "2026-05-14T09:00:00Z" : null,
        created_at: "2026-05-14T09:00:00Z",
        updated_at: "2026-05-14T09:00:00Z",
      }
      mockManuscriptAnnotations.unshift(created)
      return json(route, created)
    }

    const annotationDeleteMatch = path.match(/^\/api\/v1\/books\/book-1\/annotations\/([^/]+)$/)
    if (annotationDeleteMatch && method === "DELETE") {
      const annotationId = annotationDeleteMatch[1]
      const index = mockManuscriptAnnotations.findIndex((annotation: typeof mockManuscriptAnnotations[number]) => annotation.id === annotationId)
      if (index >= 0) {
        mockManuscriptAnnotations.splice(index, 1)
      }
      return route.fulfill({ status: 204, body: "" })
    }

    if (path === "/api/v1/books/book-1/notes" && method === "GET") {
      return json(route, mockNotes)
    }

    if (path === "/api/v1/reader/book-1/progress" && method === "GET") {
      return json(route, {
        current_chapter: 2,
        scroll_pct: 35,
        chapters_read_count: 2,
        percent_complete: 64,
        chapters_left: 1,
      })
    }

    if (path === "/api/v1/beta-reads/upcoming" && method === "GET") {
      return json(route, {
        items: mockBetaReads.filter((item: typeof mockBetaReads[number]) => item.view_bucket === "active" || item.view_bucket === "scheduled"),
      })
    }

    if (path === "/api/v1/beta-reads" && method === "GET") {
      const bucket = url.searchParams.get("bucket")
      return json(route, {
        items: bucket ? mockBetaReads.filter((item: typeof mockBetaReads[number]) => item.view_bucket === bucket) : mockBetaReads,
      })
    }

    const betaDetailMatch = path.match(/^\/api\/v1\/beta-reads\/([^/]+)$/)
    if (betaDetailMatch && method === "GET") {
      const detail = buildBetaReadDetail(betaDetailMatch[1])
      return detail ? json(route, detail) : notFound(route)
    }

    const betaStartMatch = path.match(/^\/api\/v1\/beta-reads\/([^/]+)\/start$/)
    if (betaStartMatch && method === "POST") {
      const assignmentId = betaStartMatch[1]
      mockBetaReads = mockBetaReads.map((item: typeof mockBetaReads[number]) =>
        item.id === assignmentId
          ? {
              ...item,
              state: "in_progress",
              status_label: "In progress",
              primary_action: "Continue",
              first_opened_at: item.first_opened_at ?? "2026-05-14T13:00:00Z",
            }
          : item
      )
      const updated = mockBetaReads.find((item: typeof mockBetaReads[number]) => item.id === assignmentId)
      return updated ? json(route, updated) : notFound(route)
    }

    const betaSyncMatch = path.match(/^\/api\/v1\/beta-reads\/([^/]+)\/sync$/)
    if (betaSyncMatch && method === "POST") {
      const assignmentId = betaSyncMatch[1]
      const updated = mockBetaReads.find((item: typeof mockBetaReads[number]) => item.id === assignmentId)
      return updated ? json(route, { assignment: updated }) : notFound(route)
    }

    const betaFeedbackCreateMatch = path.match(/^\/api\/v1\/beta-reads\/([^/]+)\/feedback-items$/)
    if (betaFeedbackCreateMatch && method === "POST") {
      const assignmentId = betaFeedbackCreateMatch[1]
      const assignmentIndex = mockBetaReads.findIndex((item: typeof mockBetaReads[number]) => item.id === assignmentId)
      if (assignmentIndex < 0) return notFound(route)

      const payload = route.request().postDataJSON() as Record<string, unknown>
      const question = (mockBetaReadQuestions[assignmentId] ?? []).find((item: { id: string }) => item.id === payload.question_id)
      const feedbackItem = {
        id: `${assignmentId}-feedback-${Date.now()}`,
        kind: String(payload.kind || "chapter_comment"),
        chapter_number: payload.chapter_number ? Number(payload.chapter_number) : null,
        scene_id: payload.scene_id ? String(payload.scene_id) : null,
        scene_title: null,
        question_id: question?.id ?? null,
        question_prompt: question?.prompt ?? null,
        reaction: payload.reaction ? String(payload.reaction) : null,
        anchor_text: payload.anchor_text ? String(payload.anchor_text) : null,
        body: payload.body ? String(payload.body) : null,
        created_at: "2026-05-14T18:00:00Z",
        updated_at: "2026-05-14T18:00:00Z",
      }

      mockBetaReadFeedbackItems[assignmentId] = [feedbackItem, ...(mockBetaReadFeedbackItems[assignmentId] ?? [])]
      mockBetaReads[assignmentIndex] = {
        ...mockBetaReads[assignmentIndex],
        feedback_item_count: mockBetaReadFeedbackItems[assignmentId].length,
        answered_question_count: mockBetaReadFeedbackItems[assignmentId].filter((item: { kind: string }) => item.kind === "answer").length,
      }
      const detail = buildBetaReadDetail(assignmentId)
      return detail ? json(route, detail, 201) : notFound(route)
    }

    const betaFeedbackDeleteMatch = path.match(/^\/api\/v1\/beta-reads\/([^/]+)\/feedback-items\/([^/]+)$/)
    if (betaFeedbackDeleteMatch && method === "DELETE") {
      const assignmentId = betaFeedbackDeleteMatch[1]
      const feedbackItemId = betaFeedbackDeleteMatch[2]
      const assignmentIndex = mockBetaReads.findIndex((item: typeof mockBetaReads[number]) => item.id === assignmentId)
      if (assignmentIndex < 0) return notFound(route)

      mockBetaReadFeedbackItems[assignmentId] = (mockBetaReadFeedbackItems[assignmentId] ?? []).filter((item: { id: string }) => item.id !== feedbackItemId)
      mockBetaReads[assignmentIndex] = {
        ...mockBetaReads[assignmentIndex],
        feedback_item_count: mockBetaReadFeedbackItems[assignmentId].length,
        answered_question_count: mockBetaReadFeedbackItems[assignmentId].filter((item: { kind: string }) => item.kind === "answer").length,
      }
      const detail = buildBetaReadDetail(assignmentId)
      return detail ? json(route, detail) : notFound(route)
    }

    const betaSubmitMatch = path.match(/^\/api\/v1\/beta-reads\/([^/]+)\/submit-feedback$/)
    if (betaSubmitMatch && method === "POST") {
      const assignmentId = betaSubmitMatch[1]
      const payload = route.request().postDataJSON() as { final_rating?: number } | null
      mockBetaReads = mockBetaReads.map((item: typeof mockBetaReads[number]) =>
        item.id === assignmentId
          ? {
              ...item,
              state: "completed",
              view_bucket: "completed",
              status_label: "Completed",
              primary_action: "View",
              submitted_at: "2026-05-14T18:30:00Z",
              completed_at: "2026-05-14T18:31:00Z",
              final_rating: payload?.final_rating ?? 4,
              submission_allowed: false,
            }
          : item
      )
      const updated = mockBetaReads.find((item: typeof mockBetaReads[number]) => item.id === assignmentId)
      return updated ? json(route, updated) : notFound(route)
    }

    const betaRevokeMatch = path.match(/^\/api\/v1\/books\/book-1\/beta-reads\/([^/]+)\/revoke$/)
    if (betaRevokeMatch && method === "POST") {
      const assignmentId = betaRevokeMatch[1]
      mockBetaReads = mockBetaReads.map((item: typeof mockBetaReads[number]) =>
        item.id === assignmentId
          ? {
              ...item,
              state: "revoked",
              view_bucket: "missed",
              status_label: "Revoked",
              primary_action: "View",
              revoked_at: "2026-05-14T16:00:00Z",
              revoked_reason: "revoked_by_author",
            }
          : item
      )
      const updated = mockBetaReads.find((item: typeof mockBetaReads[number]) => item.id === assignmentId)
      return updated ? json(route, updated) : notFound(route)
    }

    if (path === "/api/v1/reader/book-1/chapters" && method === "GET") {
      return json(route, chapterList)
    }

    if (path === "/api/v1/reader/book-1/relationships" && method === "GET") {
      return json(route, relationshipGraph)
    }

    const chapterMatch = path.match(/^\/api\/v1\/reader\/book-1\/chapter\/(\d+)$/)
    if (chapterMatch && method === "GET") {
      const chapterNumber = Number.parseInt(chapterMatch[1] ?? "", 10)
      const chapterData = chaptersByNumber[chapterNumber as keyof typeof chaptersByNumber]
      return chapterData ? json(route, chapterData) : notFound(route)
    }

    if (path === "/api/v1/reader/book-1/plot-threads" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/intelligence/book-1/advisor/synopsis" && method === "GET") {
      return json(route, synopsis)
    }

    if (path === "/api/v1/intelligence/book-1/advisor/suggestions" && method === "GET") {
      return json(route, {
        suggestions: [
          {
            id: "thread-1",
            type: "dropped_thread",
            severity: "warning",
            title: 'Unresolved thread: "Who opened the gate?"',
            description: "Introduced at chapter 1, still open after the bridge sequence.",
            chapter_ref: 1,
            action_label: "Ask advisor about this thread",
            ask_prompt: "Is there a plothole or missed opportunity with the gate mystery?",
            source: "heuristic",
          },
        ],
        total: 1,
        book_title: book.title,
        meta: {
          character_count: 4,
          state_count: 3,
          open_thread_count: 1,
          clue_count: 2,
          relationship_count: 2,
          world_element_count: 1,
          heuristic_count: 1,
          fallback_applied: false,
          proactive_audit_applied: true,
          scan_basis: ["characters", "character_states", "plot_threads", "chapter_summaries", "relationships", "world_elements"],
          data_gaps: [],
          audit_summary: "The gate mystery is still carrying the highest proactive risk in the current draft.",
        },
      })
    }

    if (path === "/api/v1/intelligence/book-1/advisor/voice-consistency" && method === "POST") {
      return json(route, voiceConsistency)
    }

    if (path === "/api/v1/intelligence/book-1/world-building/documents" && method === "GET") {
      return json(route, worldBuildingDocuments)
    }

    if (path === "/api/v1/intelligence/book-1/world-building/documents/world-doc-1" && method === "GET") {
      return json(route, worldBuildingDocumentDetail)
    }

    if (path === "/api/v1/intelligence/book-1/world-building/notes" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/intelligence/book-1/world-building/wiki" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/intelligence/book-1/world-building/elements" && method === "GET") {
      return json(route, worldElements)
    }

    if (path === "/api/v1/intelligence/book-1/world-building/canon-overrides" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/intelligence/book-1/world-building/gaps" && method === "GET") {
      return json(route, worldGapAnalysis)
    }

    if (path === "/api/v1/public/forum/posts" && method === "GET") {
      return json(route, { items: publicForumPosts, total: publicForumPosts.length, page: 1, page_size: 20, has_more: false })
    }

    if (path === "/api/v1/public/books" && method === "GET") {
      return json(route, publicBooks)
    }

    const publicBookMatch = path.match(/^\/api\/v1\/public\/books\/([^/]+)$/)
    if (publicBookMatch && method === "GET") {
      const detail = publicBookDetails[publicBookMatch[1] as keyof typeof publicBookDetails]
      return detail ? json(route, detail) : notFound(route)
    }

    const publicChapterMatch = path.match(/^\/api\/v1\/public\/books\/([^/]+)\/chapter\/(\d+)$/)
    if (publicChapterMatch && method === "GET") {
      const chapter = publicChapters[`${publicChapterMatch[1]}:${publicChapterMatch[2]}` as keyof typeof publicChapters]
      return chapter ? json(route, chapter) : notFound(route)
    }

    if (path === "/api/v1/public/forum/posts/forum-post-1" && method === "GET") {
      return json(route, publicForumPosts[0])
    }

    if (path === "/api/v1/public/forum/posts/forum-post-1/comments" && method === "GET") {
      return json(route, { items: publicForumComments })
    }

    if (path === "/api/v1/public/forum/posts/forum-post-1/comments" && method === "POST") {
      const payload = route.request().postDataJSON() as { body?: string } | null
      const created = {
        id: `forum-comment-${publicForumComments.length + 1}`,
        post_id: "forum-post-1",
        book_id: "book-1",
        author_user_id: "user-1",
        author_username: "author",
        author_reputation_score: 18,
        author_trust_level: "Trusted",
        body: payload?.body ?? "",
        like_count: 0,
        dislike_count: 0,
        reaction: null,
        can_edit: true,
        created_at: "2026-05-14T13:00:00Z",
        updated_at: "2026-05-14T13:00:00Z",
      }
      publicForumComments = [...publicForumComments, created]
      publicForumPosts[0].comment_count = publicForumComments.length
      return json(route, created, 201)
    }

    const publicCommentReactionMatch = path.match(/^\/api\/v1\/public\/forum\/comments\/([^/]+)\/reaction$/)
    if (publicCommentReactionMatch && method === "PUT") {
      const payload = route.request().postDataJSON() as { reaction?: "like" | "dislike" | "clear" } | null
      const commentId = publicCommentReactionMatch[1]
      publicForumComments = publicForumComments.map((comment) => {
        if (comment.id !== commentId) return comment
        const previous = comment.reaction
        const next = payload?.reaction === "clear" ? null : (payload?.reaction ?? null)
        return {
          ...comment,
          reaction: next,
          like_count: previous === "like" && next !== "like" ? Math.max(0, comment.like_count - 1) : previous !== "like" && next === "like" ? comment.like_count + 1 : comment.like_count,
          dislike_count: previous === "dislike" && next !== "dislike" ? Math.max(0, comment.dislike_count - 1) : previous !== "dislike" && next === "dislike" ? comment.dislike_count + 1 : comment.dislike_count,
        }
      })
      const updated = publicForumComments.find((comment) => comment.id === commentId)
      return updated ? json(route, updated) : notFound(route)
    }

    const publicUserMatch = path.match(/^\/api\/v1\/public\/users\/([^/]+)$/)
    if (publicUserMatch && method === "GET") {
      const profile = publicWriterProfiles[decodeURIComponent(publicUserMatch[1]) as keyof typeof publicWriterProfiles]
      return profile ? json(route, profile) : notFound(route)
    }

    if (path.startsWith("/api/v1/")) {
      return notFound(route)
    }

    return route.continue()
  })
}
