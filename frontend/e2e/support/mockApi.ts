import type { Page, Route } from "@playwright/test"
import type { Character } from "@/types/character"
import type { EmailPreferences } from "@/types/email"
import type { PublicBook, RevisionIntelligence } from "@/types/book"
import type { PublicForumPost } from "@/types/public"

type SessionMode = "authenticated" | "guest"
type LoginMode = "success" | "unauthorized"
type AdminMode = "none" | "moderation" | "billing" | "super" | "owner"
type VoiceConsistencyMode = "success" | "backend-error" | "weak-attribution" | "selected-character"
type CharacterBibleMode = "default" | "review-only"
type ManuscriptProcessingMode = "default" | "refresh-after-two-book-reads" | "allowance-paused"
type UserTierMode = "author" | "free"

type MockOptions = {
  session?: SessionMode
  login?: LoginMode
  admin?: AdminMode
  voiceConsistency?: VoiceConsistencyMode
  characterBible?: CharacterBibleMode
  manuscriptProcessing?: ManuscriptProcessingMode
  userTier?: UserTierMode
  activationPending?: boolean
}

const ADMIN_TEST_SESSION_COOKIE = "lorevia_admin_test_session"
const ADMIN_TEST_SESSION_SECRET = process.env.ADMIN_E2E_TEST_SECRET ?? "codex-e2e-admin-secret"
const ACCESS_TOKEN_COOKIE = "lorevia_access_token"
const REFRESH_TOKEN_COOKIE = "lorevia_refresh_token"
const E2E_APP_ORIGIN = "http://localhost:3001"

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
  messaging_permission: "anyone",
  created_at: "2026-04-01T09:00:00Z",
}

const defaultUsername = user.username

const book = {
  id: "book-1",
  title: "Sky of Ash",
  author: "M. Vale",
  genre: "Epic Fantasy",
  format: "docx",
  work_type: "novel",
  status: "ready",
  mode: "author",
  workspace_shell: "author",
  access_class: "owner",
  source_kind: "upload",
  preserve_chapter_numbers: true,
  cover_url: "/api/v1/books/book-1/cover?token=mock-cover",
  total_chapters: 3,
  total_tokens: 42000,
  total_words: 31500,
  is_truncated: false,
  primary_series_id: null,
  series_name: "Ash Cycle",
  series_order: 1,
  is_public: false,
  public_description: "A storm-lashed fantasy about a gate city, a vanished oath, and the cost of holding the wall.",
  copyright_warning: false,
  archived_at: null,
  hidden_at: null as string | null,
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

const initialPublicForumPosts: PublicForumPost[] = [
  {
    id: "forum-post-1",
    thread_type: "novel",
    book_id: "book-1",
    author_user_id: "user-1",
    author_username: "author",
    author_reputation_score: 18,
    author_trust_level: "Trusted",
  title: "Sky of Ash",
  author: "M. Vale",
  genre: "Epic Fantasy",
  description: "A storm-lashed fantasy about a gate city, a vanished oath, and the cost of holding the wall.",
  work_type: "novel",
    headline: "Looking for sharp beta readers for an ash-storm fantasy.",
    body: "I need readers who can flag pacing drift, trust weak scenes, and tell me where momentum slips before the midpoint.",
    desired_beta_reader_count: 5,
    allow_contact_requests: true,
    status: "open",
    viewer_interest_status: null,
    reaction: null,
    interest_count: 3,
    comment_count: 2,
    like_count: 6,
    dislike_count: 1,
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
  {
    id: "forum-post-2",
    thread_type: "general",
    book_id: null,
    author_user_id: "reader-1",
    author_username: "beta_reader",
    author_reputation_score: 9,
    author_trust_level: "Trusted",
  title: null,
  author: null,
  genre: null,
  description: null,
  work_type: null,
    headline: "How do you keep second acts from flattening out?",
    body: "Looking for practical advice on keeping a long middle section tense without rushing character payoffs.",
    desired_beta_reader_count: null,
    allow_contact_requests: false,
    status: "open",
    viewer_interest_status: null,
    reaction: null,
    interest_count: 0,
    comment_count: 1,
    like_count: 2,
    dislike_count: 0,
    rating_summary: {
      average_rating: null,
      rating_count: 0,
      positive_rating_count: 0,
      neutral_rating_count: 0,
      negative_rating_count: 0,
    },
    discoverability_score: 16,
    created_at: "2026-05-14T10:00:00Z",
    updated_at: "2026-05-14T10:30:00Z",
  },
]

let publicForumPosts: PublicForumPost[] = JSON.parse(JSON.stringify(initialPublicForumPosts))

const supplementalForumPosts: PublicForumPost[] = Array.from({ length: 22 }, (_, index) => ({
  id: `forum-seed-${index + 1}`,
  thread_type: index % 2 === 0 ? "general" : "novel",
  book_id: null,
  author_user_id: `seed-user-${index + 1}`,
  author_username: `seed_writer_${index + 1}`,
  author_reputation_score: 2 + index,
  author_trust_level: index % 3 === 0 ? "Trusted" : "New member",
  title: index % 2 === 0 ? null : `Seed Book ${index + 1}`,
  author: index % 2 === 0 ? null : `Seed Author ${index + 1}`,
  genre: index % 2 === 0 ? null : "Fantasy",
  description: index % 2 === 0 ? null : `Seed fantasy project description ${index + 1}.`,
  work_type: index % 2 === 0 ? null : "novel",
  headline: `Seed forum headline ${index + 1}`,
  body: `Supplemental forum discussion ${index + 1} for pagination coverage in the public forum feed.`,
  desired_beta_reader_count: index % 2 === 0 ? null : 3,
  allow_contact_requests: index % 2 !== 0,
  status: "open",
  viewer_interest_status: null,
  reaction: null,
  interest_count: index % 2 === 0 ? 0 : 1,
  comment_count: index % 4,
  like_count: 1 + index,
  dislike_count: 0,
  rating_summary: {
    average_rating: index % 2 === 0 ? null : 4.1,
    rating_count: index % 2 === 0 ? 0 : 2,
    positive_rating_count: index % 2 === 0 ? 0 : 2,
    neutral_rating_count: 0,
    negative_rating_count: 0,
  },
  discoverability_score: 15 - (index * 0.25),
  created_at: `2026-05-${String((index % 9) + 1).padStart(2, "0")}T09:00:00Z`,
  updated_at: `2026-05-${String((index % 9) + 1).padStart(2, "0")}T10:00:00Z`,
}))

function buildForumFeedPosts() {
  return [...publicForumPosts, ...supplementalForumPosts]
}

function filterForumFeedPosts(posts: PublicForumPost[], query: string | null) {
  const normalizedQuery = (query || "").trim().toLowerCase()
  if (!normalizedQuery) {
    return posts
  }
  return posts.filter((post) =>
    [
      post.title,
      post.author,
      post.author_username,
      post.genre,
      post.headline,
      post.body,
    ]
      .filter((value): value is string => typeof value === "string" && value.length > 0)
      .some((value) => value.toLowerCase().includes(normalizedQuery)),
  )
}

const initialPublicForumComments: Array<{
  id: string
  post_id: string
  book_id: string | null
  parent_comment_id: string | null
  author_user_id: string
  author_username: string | null
  author_reputation_score: number
  author_trust_level: string
  body: string
  like_count: number
  dislike_count: number
  reaction: "like" | "dislike" | null
  can_edit: boolean
  replies: Array<unknown>
  created_at: string
  updated_at: string
}> = [
  {
    id: "forum-comment-1",
    post_id: "forum-post-1",
    book_id: "book-1",
    parent_comment_id: null,
    author_user_id: "reader-1",
    author_username: "beta_reader",
    author_reputation_score: 9,
    author_trust_level: "Trusted",
    body: "The pitch is strong. I’d focus my notes on whether the opening stakes land before chapter two.",
    like_count: 4,
    dislike_count: 0,
    reaction: null,
    can_edit: false,
    replies: [],
    created_at: "2026-05-14T09:00:00Z",
    updated_at: "2026-05-14T09:00:00Z",
  },
  {
    id: "forum-comment-2",
    post_id: "forum-post-1",
    book_id: "book-1",
    parent_comment_id: null,
    author_user_id: "reader-2",
    author_username: "line_editor",
    author_reputation_score: 4,
    author_trust_level: "New member",
    body: "I’d also watch how much lore arrives before the first personal conflict turns visible on the page.",
    like_count: 2,
    dislike_count: 0,
    reaction: null,
    can_edit: false,
    replies: [],
    created_at: "2026-05-14T09:30:00Z",
    updated_at: "2026-05-14T09:30:00Z",
  },
  {
    id: "forum-comment-3",
    post_id: "forum-post-2",
    book_id: null,
    parent_comment_id: null,
    author_user_id: "user-1",
    author_username: "author",
    author_reputation_score: 18,
    author_trust_level: "Trusted",
    body: "I try to make every middle-chapter scene either cash in the premise or threaten it.",
    like_count: 3,
    dislike_count: 0,
    reaction: null,
    can_edit: true,
    replies: [],
    created_at: "2026-05-14T11:00:00Z",
    updated_at: "2026-05-14T11:00:00Z",
  },
]

let publicForumComments: Array<{
  id: string
  post_id: string
  book_id: string | null
  parent_comment_id: string | null
  author_user_id: string
  author_username: string | null
  author_reputation_score: number
  author_trust_level: string
  body: string
  like_count: number
  dislike_count: number
  reaction: "like" | "dislike" | null
  can_edit: boolean
  replies: Array<unknown>
  created_at: string
  updated_at: string
}> = JSON.parse(JSON.stringify(initialPublicForumComments))

function buildNestedForumComments(postId: string) {
  const postComments = publicForumComments
    .filter((comment) => comment.post_id === postId)
    .sort((left, right) => left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id))
    .map((comment) => ({ ...comment, replies: [] as typeof publicForumComments }))
  const commentMap = new Map(postComments.map((comment) => [comment.id, comment]))
  const roots: typeof postComments = []

  for (const comment of postComments) {
    if (comment.parent_comment_id && commentMap.has(comment.parent_comment_id)) {
      commentMap.get(comment.parent_comment_id)?.replies.push(comment)
      continue
    }
    roots.push(comment)
  }

  return roots
}

function countForumComments(postId: string) {
  return publicForumComments.filter((comment) => comment.post_id === postId).length
}

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
      forum_post_id: "forum-post-1",
      public_book_id: "public-book-1",
    },
    public_books_count: 1,
    public_books: [
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
        active_forum_post_id: "forum-post-1",
        published_at: "2026-05-14T08:00:00Z",
        analytics: {
          book_view_count: 186,
          unique_reader_count_30d: 71,
          chapter_view_count: 244,
          published_at: "2026-05-14T08:00:00Z",
          chapter_count: 1,
          total_words: 2450,
          has_open_discussion: true,
          open_discussion_count: 1,
          discussion_comment_count: 2,
          discussion_interest_count: 3,
        },
      },
    ],
    public_analytics: {
      total_book_views: 186,
      total_unique_readers_30d: 71,
      total_chapter_views: 244,
      total_public_books: 1,
      total_chapters: 1,
      total_words: 2450,
      latest_published_at: "2026-05-14T08:00:00Z",
      open_forum_discussions_count: 1,
    },
    posts: [
      {
        id: "forum-post-1",
        thread_type: "novel",
        status: "open",
        headline: "Looking for sharp beta readers for an ash-storm fantasy.",
        body: "I need readers who can flag pacing drift, trust weak scenes, and tell me where momentum slips before the midpoint.",
        title: "Sky of Ash",
        genre: "Epic Fantasy",
        work_type: "novel",
        book_id: "book-1",
        comment_count: 2,
        interest_count: 3,
        like_count: 6,
        dislike_count: 0,
        created_at: "2026-05-14T08:00:00Z",
        updated_at: "2026-05-14T12:00:00Z",
      },
      {
        id: "forum-post-3",
        thread_type: "novel",
        status: "closed",
        headline: "Closed thread for revision-round readers.",
        body: "This beta round is wrapped, but I am keeping the notes visible for future readers.",
        title: "Sky of Ash",
        genre: "Epic Fantasy",
        work_type: "novel",
        book_id: "book-1",
        comment_count: 1,
        interest_count: 0,
        like_count: 1,
        dislike_count: 0,
        created_at: "2026-05-10T08:00:00Z",
        updated_at: "2026-05-11T10:00:00Z",
      },
    ],
    comments: [
      {
        id: "forum-comment-4",
        post_id: "forum-post-2",
        thread_type: "general",
        post_status: "open",
        post_headline: "How do you keep second acts from flattening out?",
        post_title: null,
        book_id: null,
        body: "I usually tighten the promise of the midpoint so every scene is either earning or delaying that turn.",
        like_count: 7,
        dislike_count: 1,
        created_at: "2026-05-14T11:00:00Z",
        updated_at: "2026-05-14T11:00:00Z",
      },
    ],
    created_at: "2026-04-01T09:00:00Z",
  },
}

const publicBooks: PublicBook[] = [
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
    active_forum_post_id: "forum-post-1",
    created_at: "2026-05-14T08:00:00Z",
    published_at: "2026-05-14T08:00:00Z",
    public_updated_at: "2026-05-20T08:00:00Z",
    analytics: {
      book_view_count: 128,
      unique_reader_count_30d: 64,
      chapter_view_count: 212,
      published_at: "2026-05-14T08:00:00Z",
      chapter_count: 1,
      total_words: 1800,
      has_open_discussion: true,
      open_discussion_count: 1,
      discussion_comment_count: 7,
      discussion_interest_count: 3,
    },
  },
]

const publicUploadsOverview = {
  total_public_books: publicBooks.length,
  total_authors: new Set(publicBooks.map((book) => book.author_username || book.author)).size,
  total_visible_chapters: publicBooks.reduce((total, book) => total + (book.analytics?.chapter_count ?? book.total_chapters ?? 0), 0),
  total_visible_words: publicBooks.reduce((total, book) => total + (book.analytics?.total_words ?? 0), 0),
  uploads_last_30_days: publicBooks.length,
  genre_breakdown: [{ label: "Epic Fantasy", count: 1 }],
  work_type_breakdown: [{ label: "Novel", count: 1 }],
  recent_uploads: publicBooks,
}

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
    { number: 1, title: "Ashfall", word_count: 10400, processed: true, intelligence_available: true, read: true },
    { number: 2, title: "The Ember Gate", word_count: 11200, processed: true, intelligence_available: true, read: true },
    { number: 3, title: "River of Glass", word_count: 9900, processed: false, intelligence_available: false, read: false },
  ],
}

let mockReadingProgress = {
  current_chapter: 2,
  scroll_pct: 35,
  chapters_read_count: 2,
  percent_complete: 64,
  chapters_left: 1,
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
  media: [
    {
      marker: "[[IMAGE:1]]",
      asset_type: "image",
      content_type: "image/png",
      sort_order: 0,
      url: "/api/v1/reader/media/media-inline-1?token=inline-token",
      caption: "Ash bridge sketch",
      content_base64: null,
    },
    {
      marker: "[[IMAGE:2]]",
      asset_type: "image",
      content_type: "image/png",
      sort_order: 1,
      url: null,
      content_base64: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAukB9VE3d2QAAAAASUVORK5CYII=",
      caption: "Fallback inset",
    },
  ],
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
    media: [
      {
        marker: "[[IMAGE:0]]",
        asset_type: "image",
        content_type: "image/png",
        sort_order: 0,
        url: "/api/v1/reader/media/media-inline-0?token=inline-token",
        caption: "Cover illustration panel",
        content_base64: null,
      },
    ],
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
    media: [
      {
        marker: "[[IMAGE:3]]",
        asset_type: "image",
        content_type: "image/png",
        sort_order: 0,
        url: "/api/v1/reader/media/media-inline-3?token=inline-token",
        caption: "River map",
        content_base64: null,
      },
    ],
    characters: chapter.characters,
  },
} as const

const characterReviewPayload = {
  candidates: [
    {
      id: "candidate-1",
      book_id: "book-1",
      chapter_number: 2,
      raw_name: "Gregor's sister",
      proposed_name: "Gregor's sister",
      normalized_name: "gregor sister",
      aliases: [],
      matched_character_id: "char-grete",
      status: "pending",
      confidence: 61,
      reason_codes: ["possible_role_label", "needs_review"],
      evidence: {},
      dossier_summary: {
        mention_count: 1,
        distinct_chapter_count: 1,
        strict_auto_eligible: false,
        strict_auto_reason_codes: ["role_only_reference", "insufficient_cross_chapter_support"],
      },
      source_batch_key: "batch-1",
      created_at: "2026-05-14T10:00:00Z",
      updated_at: "2026-05-14T10:00:00Z",
    },
  ],
  duplicate_suggestions: [
    {
      id: "duplicate-1",
      book_id: "book-1",
      primary_character_id: "char-grete",
      secondary_character_id: "char-gregors-sister",
      confidence: 92,
      reasons: ["Exact name overlap in scene context"],
      shared_evidence: {},
      status: "pending",
      created_at: "2026-05-14T10:00:00Z",
      updated_at: "2026-05-14T10:00:00Z",
    },
  ],
  relationship_candidates: [
    {
      id: "rel-candidate-1",
      book_id: "book-1",
      chapter_number: 3,
      raw_character_a: "Grete",
      raw_character_b: "Gregor's father",
      matched_character_a_id: "char-grete",
      matched_character_b_id: "char-mr-samsa",
      rel_type: "family",
      sentiment: -0.4,
      description: "Strain grows as the household turns defensive.",
      status: "pending",
      reason_codes: ["relationship_unresolved", "character_a_resolved", "character_b_resolved"],
      evidence: {},
      source_batch_key: "relationship-batch-1",
      created_at: "2026-05-14T10:00:00Z",
      updated_at: "2026-05-14T10:00:00Z",
    },
  ],
  shadow_characters: [
    {
      id: "char-gregors-sister",
      book_id: "book-1",
      name: "Gregor's sister",
      aliases: [],
      role: null,
      first_chapter: 2,
      last_seen_chapter: 2,
      mention_count: 1,
      analysis_metadata: {
        approval_state: "pending_review",
        approval_source: "backfill_review",
        approval_reason_codes: ["role_only_reference"],
        trust_tier: "review_only",
        trust_reasons: ["role_only_single_token"],
      },
      is_manual: false,
    },
  ],
  decision_events: [
    {
      id: "decision-1",
      book_id: "book-1",
      character_id: "char-gregors-sister",
      actor_user_id: null,
      action: "character_demoted_for_review",
      visibility_state: "quarantined",
      approval_state: "pending_review",
      approval_source: "backfill_review",
      reason_codes: ["role_only_reference"],
      evidence: {},
      created_at: "2026-05-14T10:00:00Z",
    },
  ],
  counts: {
    pending_candidates: 1,
    pending_duplicate_suggestions: 1,
    pending_relationship_candidates: 1,
  },
}

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
  novel_preface: "A short note before the ash gates open.",
  novel_front_matter: {
    dedication: "",
    acknowledgements: "",
    copyright_page: "",
    about_author: "",
    series_book_list: "",
  },
  novel_epub_metadata: {
    publisher: "",
    language: "en",
    isbn: "",
    description: "",
    series_name: "",
    series_number: "",
  },
  revision_board: {
    items: [],
    last_generated_at: null,
  },
  reprocess: {
    auto_reprocess_enabled: true,
    pending_chapters: [],
    last_mode_changed_at: null,
    last_manual_chapter_started_at: null,
    last_manual_chapter_number: null,
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
      detail: "Nora enters the city and hears the bells.",
    },
  ],
  alerts: [
    {
      type: "world_gap",
      severity: "medium",
      title: "Northreach canon note is still thin",
      description: "The current world corpus still needs stronger canon detail for Northreach before later continuity checks.",
      chapter_number: 2,
    },
    {
      type: "world_gap",
      severity: "medium",
      title: "Glass Road needs one more anchor",
      description: "Readers only get a light setup for Glass Road before later references depend on it.",
      chapter_number: 2,
    },
  ],
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

const vaultNotes = [
  {
    id: "vault-note-1",
    book_id: "book-1",
    path: "Manual Editor/Chapter 2/Gate imagery.md",
    source: "manual_editor",
    content: "# Gate imagery\n\nRevisit the bell motif.",
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

const initialCollaborators = [
  {
    id: "collab-1",
    book_id: "book-1",
    email: "beta@example.com",
    display_name: "Ari Reader",
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

const collaborators = JSON.parse(JSON.stringify(initialCollaborators))

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
  warnings: [],
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

const selectedCharacterVoiceConsistency = {
  review: {
    overall_verdict: "Gregor's voice holds together, but one beat drifts toward explanation over reaction.",
    issues: [
      {
        character_name: "Gregor",
        severity: "moderate",
        title: "Gregor slips into abstract explanation",
        description: "The passage briefly trades Gregor's self-effacing immediacy for a cooler, more analytical sentence.",
        evidence: "Gregor usually sounds careful and inward, even when he is rationalizing what the family needs from him.",
        suggestion: "Keep the line closer to Gregor's anxious interior voice and shorten the explanatory phrasing.",
        intentionality_prompt: "If the shift is intentional, add a clearer cue that Gregor is distancing himself from the moment.",
      },
    ],
  },
  retrieved_passages: [],
  characters_reviewed: ["Gregor"],
  warnings: [],
  character_matches: [
    {
      character_name: "Gregor",
      match_score: 74,
      baseline_sample_size: 5,
      sample_dialogue_count: 2,
      strongest_signals: ["careful cadence", "self-effacing phrasing"],
      closest_other_character: "Grete",
      closest_other_score: 38,
    },
  ],
}

const weakAttributionVoiceConsistency = {
  review: {
    overall_verdict: "Grete's emotional line still reads coherently, but the attribution signal is thin in this excerpt.",
    issues: [],
  },
  retrieved_passages: [],
  characters_reviewed: ["Grete"],
  warnings: ["Dialogue could not be confidently attributed to Grete; the review used the full submitted passage instead."],
  character_matches: [
    {
      character_name: "Grete",
      match_score: 61,
      baseline_sample_size: 4,
      sample_dialogue_count: 1,
      strongest_signals: ["higher emotional pressure", "broader phrasing"],
      closest_other_character: "Gregor",
      closest_other_score: 41,
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

function buildAdminSession(admin: AdminMode) {
  switch (admin) {
    case "moderation":
      return {
        is_admin: true,
        scopes: ["moderation_admin"],
        is_owner: false,
        requires_step_up: true,
        session_expires_at: null,
      }
    case "billing":
      return {
        is_admin: true,
        scopes: ["billing_admin"],
        is_owner: false,
        requires_step_up: true,
        session_expires_at: null,
      }
    case "super":
      return {
        is_admin: true,
        scopes: ["super_admin"],
        is_owner: false,
        requires_step_up: true,
        session_expires_at: null,
      }
    case "owner":
      return {
        is_admin: true,
        scopes: ["moderation_admin", "billing_admin", "super_admin"],
        is_owner: true,
        requires_step_up: false,
        session_expires_at: null,
      }
    default:
      return null
  }
}

export async function installMockApi(page: Page, options: MockOptions = {}) {
  const session = options.session ?? "authenticated"
  const login = options.login ?? "success"
  const admin = options.admin ?? "none"
  const voiceConsistencyMode = options.voiceConsistency ?? "success"
  const characterBibleMode = options.characterBible ?? "default"
  const manuscriptProcessingMode = options.manuscriptProcessing ?? "default"
  let activationRevision = (options.activationPending
    ? {
        ...revisionIntelligence,
        priority_findings: [
          {
            ...revisionIntelligence.change_impacts[0],
            why_flagged: revisionIntelligence.change_impacts[0].description,
            evidence_strength: "strong",
            evidence: [{ chapter_ref: 2, source_label: "The Ember Gate", excerpt: "Nora crossed the silver gate without the blood oath Kael expected.", source_content_version: 2 }],
            is_stale: false,
          },
          {
            ...revisionIntelligence.scene_advice[0],
            why_flagged: revisionIntelligence.scene_advice[0].description,
            evidence_strength: "moderate",
            evidence: [{ chapter_ref: 3, source_label: "River of Glass", excerpt: "The gate warning returned before the reveal moved forward.", source_content_version: 1 }],
            is_stale: false,
          },
          {
            ...revisionIntelligence.confusion_map[0],
            why_flagged: revisionIntelligence.confusion_map[0].description,
            evidence_strength: "moderate",
            evidence: [{ chapter_ref: 1, source_label: "Ashfall", excerpt: "Four names arrived with the first ashfall bulletin.", source_content_version: 1 }],
            is_stale: false,
          },
        ],
        activation: { eligible: true, completed: false, completed_at: null, completion_action: null, completed_finding_id: null },
        analysis_complete: true,
        analysis_limitations: [],
      }
    : {
        ...revisionIntelligence,
        priority_findings: [],
        activation: { eligible: false, completed: true, completed_at: "2026-05-01T00:00:00Z", completion_action: "added_to_revision_plan", completed_finding_id: "rev-impact-1" },
        analysis_complete: true,
        analysis_limitations: [],
      }) as unknown as RevisionIntelligence
  book.hidden_at = null
  book.is_public = false
  const mockUser = {
    ...user,
    username: defaultUsername,
    ...(options.userTier === "free"
      ? {
          tier: "free",
          plan_tier: "free",
          tier_label: "Free",
          trial_active: false,
          trial_ends_at: null,
        }
      : {}),
  }
  const adminCookieMode = admin === "none" ? "guest" : admin
  const cookies = [
    {
      name: ADMIN_TEST_SESSION_COOKIE,
      value: `${adminCookieMode}:${ADMIN_TEST_SESSION_SECRET}`,
      url: E2E_APP_ORIGIN,
      httpOnly: true,
      sameSite: "Lax" as const,
    },
  ]
  if (session === "authenticated") {
    cookies.push(
      {
        name: ACCESS_TOKEN_COOKIE,
        value: "mock-access-token",
        url: E2E_APP_ORIGIN,
        httpOnly: true,
        sameSite: "Lax" as const,
      },
      {
        name: REFRESH_TOKEN_COOKIE,
        value: "mock-refresh-token",
        url: E2E_APP_ORIGIN,
        httpOnly: true,
        sameSite: "Lax" as const,
      },
    )
  }
  await page.context().clearCookies()
  await page.context().addCookies(cookies)
  
  // Populate sessionStorage with the user object to match authenticated session state.
  // This prevents a race condition on the login page: the page checks if a user exists
  // in the auth store (from sessionStorage) to decide whether to redirect. Without this,
  // the cookies are set but sessionStorage is empty, so the page doesn't know to redirect.
  // We wrap in try-catch because sessionStorage isn't accessible until the page navigates.
  try {
    if (session === "authenticated") {
      await page.evaluate((userData) => {
        window.sessionStorage.setItem("lorevia-auth-user", JSON.stringify(userData))
      }, mockUser)
    } else {
      await page.evaluate(() => {
        window.sessionStorage.removeItem("lorevia-auth-user")
      })
    }
  } catch (error) {
    // SessionStorage not accessible yet (no document context)
    // This is fine - the auth bootstrap will handle hydration after navigation
  }
  
  publicForumPosts = JSON.parse(JSON.stringify(initialPublicForumPosts))
  publicForumComments = JSON.parse(JSON.stringify(initialPublicForumComments))
  collaborators.splice(0, collaborators.length, ...JSON.parse(JSON.stringify(initialCollaborators)))
  let mockBook = JSON.parse(JSON.stringify(book))
  let mockWriterWorkspace = JSON.parse(JSON.stringify(writerWorkspace))
  let mockNotifications = JSON.parse(JSON.stringify(notifications))
  let mockWorkspaceTree = JSON.parse(JSON.stringify(workspaceTree))
  let mockChapterList = JSON.parse(JSON.stringify(chapterList))
  let mockBetaReads = JSON.parse(JSON.stringify(initialBetaReads))
  let mockBetaReadQuestions = JSON.parse(JSON.stringify(initialBetaReadQuestions))
  let mockBetaReadFeedbackItems = JSON.parse(JSON.stringify(initialBetaReadFeedbackItems))
  let mockCharacterBibleCharacters: Character[] = characterBibleMode === "review-only"
    ? []
    : JSON.parse(JSON.stringify(characterBibleCharacters))
  let mockCharacterReviewPayload = JSON.parse(JSON.stringify(characterReviewPayload))
  let mockRelationshipGraph = JSON.parse(JSON.stringify(relationshipGraph))
  let mockNotes = JSON.parse(JSON.stringify(notes))
  let mockVaultNotes = JSON.parse(JSON.stringify(vaultNotes))
  let mockManuscriptAnnotations = JSON.parse(JSON.stringify(manuscriptAnnotations))
  let mockEmailPreferences: EmailPreferences = {
    email: mockUser.email,
    product_updates: true,
    marketing: true,
    unsubscribed_all: false,
    unsubscribed_at: null,
  }
  let bookDetailReadCount = 0
  let allowanceProcessingContinued = false

  const buildBookOverview = () => ({
    book: mockBook,
    progress: {
      current_chapter: 2,
      scroll_pct: 35,
      chapters_read_count: 2,
      percent_complete: 64,
      chapters_left: 1,
    },
    chapter_list: mockChapterList,
    summary_collection: {
      read_upto: 2,
      summaries: [
        {
          chapter_number: 1,
          chapter_title: "Ashfall",
          read: true,
          available: true,
          content: "Nora leaves the ash road and reaches the city wall.",
          key_events: [{ event: "Nora reaches the gate city.", importance: 0.88 }],
        },
        {
          chapter_number: 2,
          chapter_title: "The Ember Gate",
          read: true,
          available: true,
          content: "The ember gate opens and Nora steps into the city under watch.",
          key_events: [{ event: "The gate crossing changes the story stakes.", importance: 0.93 }],
        },
        {
          chapter_number: 3,
          chapter_title: "River of Glass",
          read: false,
          available: false,
          content: null,
          key_events: [],
        },
      ],
    },
  })

  const buildReaderBootstrap = () => ({
    overview: buildBookOverview(),
    notes: mockNotes,
    saved_quotes: [],
    stats: booksStats,
    characters: mockCharacterBibleCharacters,
    chapter_reports: [],
    prewriting_check: preWritingCheck,
    story_health: storyHealth,
    writer_workspace: mockWriterWorkspace,
    revision_intelligence: activationRevision,
  })

  const buildBookDetailResponse = () => {
    bookDetailReadCount += 1
    if (manuscriptProcessingMode === "allowance-paused" && !allowanceProcessingContinued) {
      return {
        ...mockBook,
        status: "processing",
        processing: {
          ...(mockBook.processing ?? {}),
          status: "paused",
          stage: "paused",
          progress_pct: 50,
          chapters_completed: 1,
          chapters_total: 3,
          processing_run_id: "processing-run-1",
          pause_reason: "monthly_processed_words",
          resume_available: true,
          resume_blockers: [{ kind: "monthly_processed_words", detail: "Monthly processing allowance reached." }],
          next_chapter_number: 2,
          retry_available: true,
        },
      }
    }
    if (manuscriptProcessingMode === "refresh-after-two-book-reads") {
      // The manuscript route performs multiple detail reads while the page is
      // still settling; keep one poll cycle visible before switching to ready.
      const processingActive = bookDetailReadCount <= 3
      return {
        ...mockBook,
        status: processingActive ? "processing" : "ready",
        processing: {
          ...(mockBook.processing ?? {}),
          status: processingActive ? "processing" : "ready",
          stage: processingActive ? "extracting" : "ready",
          progress_pct: processingActive ? 53 : 100,
          chapters_completed: processingActive ? 2 : 3,
          chapters_total: 3,
          eta_seconds: processingActive ? 180 : 0,
          current_step_label: processingActive ? "Extracting characters" : "Ready",
          retry_available: false,
        },
      }
    }
    return mockBook
  }

  const buildManuscriptBootstrap = () => ({
    book: buildBookDetailResponse(),
    characters: mockCharacterBibleCharacters,
    writer_workspace: mockWriterWorkspace,
    emotional_arc: emotionalArc,
    synopsis,
    workspace_tree: mockWorkspaceTree,
    annotations: mockManuscriptAnnotations,
    notes: mockNotes,
    vault_notes: mockVaultNotes,
    chapter_versions: [],
    prewriting_check: preWritingCheck,
  })

  const buildWorldBuildingBootstrap = () => ({
    documents: worldBuildingDocuments,
    selected_document: worldBuildingDocumentDetail,
    notes: [],
    canon_overrides: [],
    elements: worldElements,
    wiki: [],
    stats: booksStats,
    gap_analysis: worldGapAnalysis,
  })

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
      return session === "authenticated" ? json(route, mockUser) : json(route, { detail: "Unauthorized" }, 401)
    }

    if (path === "/api/v1/auth/session" && method === "POST") {
      return session === "authenticated" ? json(route, mockUser) : json(route, { detail: "Unauthorized" }, 401)
    }

    if (path === "/api/v1/auth/me/data-export" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/zip",
        headers: {
          "Content-Disposition": 'attachment; filename="lorevia-data-export.zip"',
        },
        body: "mock lorevia data export",
      })
    }

    if (path === "/api/v1/auth/me" && method === "DELETE") {
      return json(route, {
        ok: true,
        deletion_status: "pending_hard_delete",
        scheduled_for: "2026-06-14T00:00:00Z",
        provider_followup_required: false,
      })
    }

    if (path === "/api/v1/auth/refresh" && method === "POST") {
      return session === "authenticated" ? json(route, mockUser) : json(route, { detail: "Unauthorized" }, 401)
    }

    if (path === "/api/v1/auth/login" && method === "POST") {
      return login === "success" ? json(route, mockUser) : json(route, { detail: "Invalid credentials" }, 401)
    }

    if (path === "/api/v1/auth/logout" && method === "POST") {
      return json(route, { ok: true })
    }

    if (path === "/api/v1/admin/session" && method === "GET") {
      const adminSession = buildAdminSession(admin)
      return adminSession ? json(route, adminSession) : json(route, { detail: "Admin only" }, 403)
    }

    if (path === "/api/v1/admin/billing/status" && method === "GET") {
      return json(route, {
        billing_enabled: true,
        payments_ready: true,
        paddle_api_key_present: true,
        webhook_secret_present: true,
        default_checkout_url_present: true,
        recommended_default_checkout_url: "https://getlorevia.com/checkout",
        resend_api_key_present: true,
        internal_job_secret_present: true,
        fully_configured_plan_count: 4,
        missing_configuration: [],
        plans: [
          { code: "author_monthly", display_name: "Author", billing_interval: "monthly", price_usd: 29, configured: true, price_id_present: true },
          { code: "author_annual", display_name: "Author", billing_interval: "annual", price_usd: 249, configured: true, price_id_present: true },
          { code: "architect_monthly", display_name: "Architect", billing_interval: "monthly", price_usd: 49, configured: true, price_id_present: true },
          { code: "architect_annual", display_name: "Architect", billing_interval: "annual", price_usd: 449, configured: true, price_id_present: true },
        ],
        webhook_endpoint_path: "/api/v1/webhooks/paddle",
        supported_webhook_events: ["transaction.completed", "subscription.updated"],
        trial_email_job_endpoint_path: "/api/v1/internal/jobs/send-due-trial-emails",
        trial_email_runner_script: "backend/scripts/run_due_trial_emails.py",
        trial_email_automation_code_ready: true,
        priority_processing_code_ready: true,
        priority_queue_names: ["extraction_priority", "analysis_priority"],
        external_action_items: [],
      })
    }

    if (path === "/api/v1/admin/refunds/reviews" && method === "GET") {
      return json(route, [
        {
          id: "refund-review-1",
          user_id: "user-1",
          subscription_id: "sub-1",
          paddle_transaction_id: "txn_123",
          paddle_adjustment_id: null,
          charge_at: "2026-05-24T10:00:00Z",
          plan_code: "author_monthly",
          billing_interval: "monthly",
          request_source: "support",
          support_reference: "SUP-123",
          request_reason: "Duplicate charge report.",
          status: "manual_review_required",
          auto_decision: false,
          decision_reason: null,
          eligibility_snapshot_json: {},
          usage_snapshot_json: {},
          provider_response_json: {},
          requested_by_admin_user_id: "owner-1",
          resolved_by_admin_user_id: null,
          resolved_at: null,
          created_at: "2026-05-24T10:05:00Z",
          updated_at: "2026-05-24T10:05:00Z",
        },
      ])
    }

    if (path === "/api/v1/admin/access" && method === "GET") {
      return json(route, [
        {
          id: "principal-owner-1",
          user_id: "user-1",
          status: "active",
          is_owner: true,
          scopes: ["moderation_admin", "billing_admin", "super_admin"],
          grant_reason: "Owner bootstrap.",
          revoke_reason: null,
          granted_by_user_id: null,
          revoked_by_user_id: null,
          created_at: "2026-05-20T10:00:00Z",
          updated_at: "2026-05-20T10:00:00Z",
          revoked_at: null,
        },
      ])
    }

    if (path === "/api/v1/admin/audit" && method === "GET") {
      return json(route, [
        {
          id: "audit-1",
          actor_user_id: "user-1",
          target_user_id: "user-2",
          target_book_id: null,
          target_report_id: null,
          target_refund_review_id: null,
          action_type: "billing_status_viewed",
          reason: "Viewed billing configuration status.",
          result: "allowed",
          request_id: "req-1",
          ip_address: "127.0.0.1",
          user_agent: "playwright",
          scopes_snapshot: ["moderation_admin", "billing_admin", "super_admin"],
          metadata_json: {},
          created_at: "2026-05-24T11:00:00Z",
        },
      ])
    }

    if (path === "/api/v1/admin/public-shares/pending" && method === "GET") {
      return json(route, [
        {
          book_id: "book-1",
          user_id: "user-1",
          author_username: "author",
          title: "Sky of Ash",
          author: "M. Vale",
          genre: "Epic Fantasy",
          isbn: null,
          copyright_warning: false,
          public_description: book.public_description,
          requested_at: "2026-05-24T08:00:00Z",
          created_at: book.created_at,
        },
      ])
    }

    if (path === "/api/v1/admin/reports" && method === "GET") {
      return json(route, [
        {
          id: "report-1",
          reported_book_id: "book-1",
          reported_author_user_id: "user-1",
          reporter_user_id: "reader-1",
          reporter_email: "reader@example.com",
          report_type: "copyright",
          status: "open",
          reason: "Possible rights issue.",
          details: "Submitted for smoke coverage.",
          created_at: "2026-05-24T09:00:00Z",
        },
      ])
    }

    if (path === "/api/v1/auth/me/username" && method === "PATCH") {
      const nextUsername = url.searchParams.get("username")?.trim()
      if (!nextUsername || nextUsername.length < 3) {
        return json(route, { detail: "Username must be 3-32 characters" }, 400)
      }
      mockUser.username = nextUsername
      return json(route, mockUser)
    }

    if (path === "/api/v1/email/preferences" && method === "GET") {
      return session === "authenticated" ? json(route, mockEmailPreferences) : json(route, { detail: "Unauthorized" }, 401)
    }

    if (path === "/api/v1/email/preferences" && method === "POST") {
      const payload = route.request().postDataJSON() as { product_updates?: boolean; marketing?: boolean } | null
      mockEmailPreferences = {
        ...mockEmailPreferences,
        product_updates: Boolean(payload?.product_updates),
        marketing: Boolean(payload?.marketing),
      }
      mockEmailPreferences.unsubscribed_all = !mockEmailPreferences.product_updates && !mockEmailPreferences.marketing
      mockEmailPreferences.unsubscribed_at = mockEmailPreferences.unsubscribed_all ? "2026-05-23T12:00:00Z" : null
      return json(route, mockEmailPreferences)
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
      return json(route, book.hidden_at ? [] : [book])
    }

    if (path === "/api/v1/books/stats" && method === "GET") {
      return json(route, booksStats)
    }

    if (path === "/api/v1/books/book-1" && method === "GET") {
      return json(route, buildBookDetailResponse())
    }

    if (path === "/api/v1/books/book-1/processing/continue" && method === "POST") {
      allowanceProcessingContinued = true
      mockBook = {
        ...mockBook,
        status: "processing",
        processing: {
          ...(mockBook.processing ?? {}),
          status: "processing",
          stage: "queued",
          progress_pct: 50,
          chapters_completed: 1,
          chapters_total: 3,
          processing_run_id: "processing-run-1",
          pause_reason: null,
          resume_available: false,
          resume_blockers: [],
          next_chapter_number: 2,
          retry_available: false,
        },
      }
      return json(route, mockBook.processing)
    }

    if (path === "/api/v1/books/book-1/permanent" && method === "DELETE") {
      book.hidden_at = "2026-05-15T00:00:00Z"
      book.is_public = false
      return json(route, {
        ok: true,
        book_id: "book-1",
        deletion_request_id: "deletion-request-1",
        status: "pending",
      })
    }

    if (path === "/api/v1/books/book-1/manuscript/reprocess" && method === "POST") {
      return json(route, {
        book_id: "book-1",
        status: "processing",
        chapters_queued: 3,
        total_words: 31500,
        upload_charge_consumed: true,
        charge_kind: "manual_reprocess",
      })
    }

    if (path === "/api/v1/books/book-1/manuscript/import" && method === "POST") {
      if (mockWriterWorkspace.reprocess?.auto_reprocess_enabled === false) {
        mockWriterWorkspace.reprocess = {
          ...mockWriterWorkspace.reprocess,
          pending_chapters: Array.from(new Set([...(mockWriterWorkspace.reprocess.pending_chapters ?? []), 1])),
        }
      }
      return json(route, {
        status: "imported",
        book_id: "book-1",
        imported_chapters: [1],
        chapters_created: 1,
        analysis_dispatched: 0,
        analysis_tasks: [],
        chapter_content_versions: { 1: 3 },
        total_chapters: 3,
        mode: "author",
        source_kind: "chapter_wise",
        chapter_reports: [],
      })
    }

    if (path === "/api/v1/books/book-1/manuscript/chapters/1/reprocess" && method === "POST") {
      mockWriterWorkspace.reprocess = {
        ...(mockWriterWorkspace.reprocess ?? { auto_reprocess_enabled: false, pending_chapters: [] }),
        pending_chapters: (mockWriterWorkspace.reprocess?.pending_chapters ?? []).filter((chapter: number) => chapter !== 1),
        last_manual_chapter_number: 1,
        last_manual_chapter_started_at: "2026-06-06T00:00:00Z",
      }
      return json(route, {
        book_id: "book-1",
        status: "processing",
        chapters_queued: 1,
        total_words: 1000,
        upload_charge_consumed: false,
        charge_kind: null,
      })
    }

    if (path === "/api/v1/books/book-1/reader-bootstrap" && method === "GET") {
      return json(route, buildReaderBootstrap())
    }

    if (path === "/api/v1/books/book-1/manuscript-bootstrap" && method === "GET") {
      return json(route, buildManuscriptBootstrap())
    }

    if (path === "/api/v1/books/book-1/forum-metadata" && method === "PUT") {
      const payload = route.request().postDataJSON() as {
        title?: string
        genre?: string
        description?: string
      } | null
      mockBook.title = payload?.title ?? mockBook.title
      mockBook.genre = payload?.genre ?? mockBook.genre
      mockBook.public_description = payload?.description ?? mockBook.public_description
      publicForumPosts = publicForumPosts.map((post) => (
        post.book_id === "book-1"
          ? {
              ...post,
              title: mockBook.title,
              genre: mockBook.genre,
              description: mockBook.public_description,
            }
          : post
      ))
      return json(route, mockBook)
    }

    if (path === "/api/v1/books/book-1/overview" && method === "GET") {
      return json(route, buildBookOverview())
    }

    if (path === "/api/v1/books/book-1/collaborators" && method === "GET") {
      return json(route, collaborators)
    }

    const collaboratorActivityMatch = path.match(/^\/api\/v1\/books\/book-1\/collaborators\/([^/]+)\/activity$/)
    if (collaboratorActivityMatch && method === "GET") {
      const collaboratorId = collaboratorActivityMatch[1]
      const collaborator = collaborators.find((item: typeof collaborators[number]) => item.id === collaboratorId)
      if (!collaborator) {
        return notFound(route)
      }

      return json(route, {
        collaborator,
        assignments: mockBetaReads.filter((item: typeof mockBetaReads[number]) => item.collaborator_id === collaboratorId),
        items: [
          {
            id: `${collaboratorId}-activity-1`,
            kind: "chapter_comment",
            title: "Left chapter feedback",
            body: "Ari flagged the gate explanation as slightly repetitive.",
            chapter_number: 2,
            chapter_title: "The Ember Gate",
            assignment_id: "beta-1",
            feedback_item_id: "beta-1-feedback-1",
            annotation_id: null,
            created_at: "2026-05-14T18:00:00Z",
          },
        ],
        chapter_comment_count: 1,
        annotation_count: 0,
        latest_activity_at: "2026-05-14T18:00:00Z",
      })
    }

    if (path === "/api/v1/books/book-1/collaborators" && method === "POST") {
      const payload = JSON.parse(route.request().postData() || "{}")
      const created = {
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
      }
      collaborators.push(created)
      return json(route, created, 201)
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
      return json(route, mockCharacterBibleCharacters)
    }

    if (path === "/api/v1/books/book-1/character-review" && method === "GET") {
      return json(route, mockCharacterReviewPayload)
    }

    if (path === "/api/v1/books/book-1/character-review/reprocess" && method === "GET") {
      return json(route, {
        book_id: "book-1",
        dry_run: true,
        allow_merge_safe_pairs: true,
        allow_demote_obvious_noise: true,
        planned_merges: [["char-gregors-sister", "char-grete"]],
        planned_demotions: [],
        skipped_protected_merge_pairs: [],
        skipped_protected_demotions: [],
        updated_first_chapters: { "char-grete": 1 },
        updated_last_seen_chapters: { "char-grete": 4 },
        character_labels: { "char-gregors-sister": "Gregor's sister", "char-grete": "Grete" },
        pending_duplicate_suggestions: 0,
        pending_relationship_candidates: 1,
        pending_character_candidates_suppressed: 0,
        pending_character_candidates_kept: 1,
        pending_relationship_candidates_suppressed: 0,
        pending_relationship_candidates_kept: 1,
        protected_manual_records_skipped: 0,
        unresolved_relationship_deltas: {},
      })
    }

    if (path === "/api/v1/books/book-1/character-review/reprocess" && method === "POST") {
      return json(route, {
        book_id: "book-1",
        merged_pairs: [["char-gregors-sister", "char-grete"]],
        demoted_character_ids: [],
        skipped_protected_merge_pairs: [],
        skipped_protected_demotions: [],
        pending_character_candidates_suppressed: 0,
        pending_character_candidates_kept: 1,
        pending_relationship_candidates_suppressed: 0,
        pending_relationship_candidates_kept: 1,
        suppressed_character_candidate_ids: [],
        suppressed_relationship_candidate_ids: [],
        first_chapter_recomputes: { "char-grete": 1 },
        last_seen_chapter_recomputes: { "char-grete": 4 },
        character_labels: { "char-gregors-sister": "Gregor's sister", "char-grete": "Grete" },
        duplicate_suggestion_delta: { pending: 0 },
        unresolved_relationship_deltas: {},
      })
    }

    const relationshipReviewMatch = path.match(/^\/api\/v1\/books\/book-1\/relationship-review\/([^/]+)\/(attach-a|attach-b|accept|resolve|reject)$/)
    if (relationshipReviewMatch && method === "POST") {
      const [, candidateId, action] = relationshipReviewMatch
      const candidate = mockCharacterReviewPayload.relationship_candidates.find(
        (item: typeof mockCharacterReviewPayload.relationship_candidates[number]) => item.id === candidateId,
      )
      if (!candidate) {
        return notFound(route)
      }

      if (action === "attach-a" || action === "attach-b") {
        const payload = route.request().postDataJSON() as { character_id?: string } | null
        if (action === "attach-a") {
          candidate.matched_character_a_id = payload?.character_id ?? candidate.matched_character_a_id
        } else {
          candidate.matched_character_b_id = payload?.character_id ?? candidate.matched_character_b_id
        }
        return json(route, {
          relationship_candidate_id: candidate.id,
          [action === "attach-a" ? "attached_a" : "attached_b"]: payload?.character_id ?? null,
        })
      }

      candidate.status = action === "accept"
        ? "accepted"
        : action === "resolve"
          ? "resolved"
          : "rejected"
      mockCharacterReviewPayload.counts.pending_relationship_candidates = mockCharacterReviewPayload.relationship_candidates.filter(
        (item: typeof mockCharacterReviewPayload.relationship_candidates[number]) => item.status === "pending",
      ).length

      return json(route, {
        [action === "accept" ? "accepted" : action === "resolve" ? "resolved" : "rejected"]: candidate.id,
      })
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
        id: `char-manual-${mockCharacterBibleCharacters.length + 1}`,
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
      mockCharacterBibleCharacters.push(created)
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

    if (path === "/api/v1/books/book-1/novel/preface" && method === "PUT") {
      const body = route.request().postDataJSON() as { preface?: string } | null
      mockWriterWorkspace = {
        ...mockWriterWorkspace,
        novel_preface: body?.preface ?? "",
      }
      return json(route, { preface: mockWriterWorkspace.novel_preface })
    }

    if (path === "/api/v1/books/book-1/novel/settings" && method === "PUT") {
      const body = route.request().postDataJSON() as {
        preface?: string
        front_matter?: typeof writerWorkspace.novel_front_matter
        epub_metadata?: typeof writerWorkspace.novel_epub_metadata
      } | null
      mockWriterWorkspace = {
        ...mockWriterWorkspace,
        novel_preface: body?.preface ?? "",
        novel_front_matter: body?.front_matter ?? writerWorkspace.novel_front_matter,
        novel_epub_metadata: body?.epub_metadata ?? writerWorkspace.novel_epub_metadata,
      }
      return json(route, {
        preface: mockWriterWorkspace.novel_preface,
        front_matter: mockWriterWorkspace.novel_front_matter,
        epub_metadata: mockWriterWorkspace.novel_epub_metadata,
      })
    }

    if (path === "/api/v1/books/book-1/novel/export" && method === "GET") {
      const targetUrl = new URL(route.request().url())
      const format = targetUrl.searchParams.get("format") ?? "pdf"
      const contentType = format === "epub"
        ? "application/epub+zip"
        : format === "docx"
          ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          : "application/pdf"
      return route.fulfill({
        status: 200,
        headers: {
          "content-type": contentType,
        },
        body: Buffer.from(`mock novel ${format}`),
      })
    }

    if (path === "/api/v1/books/book-1/emotional-arc" && method === "GET") {
      return json(route, emotionalArc)
    }

    if (path === "/api/v1/books/book-1/revision-intelligence" && method === "GET") {
      return json(route, activationRevision)
    }

    if (path.match(/^\/api\/v1\/books\/book-1\/revision-findings\/[^/]+\/decision$/) && method === "POST") {
      const body = route.request().postDataJSON() as { decision?: string; action?: string } | null
      activationRevision = {
        ...activationRevision,
        activation: body?.decision === "accepted"
          ? { eligible: false, completed: true, completed_at: "2026-06-19T10:00:00Z", completion_action: body.action ?? "added_to_revision_plan", completed_finding_id: "rev-impact-1" }
          : activationRevision.activation,
      }
      return json(route, activationRevision)
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

    const chapterDeleteMatch = path.match(/^\/api\/v1\/books\/book-1\/chapters\/(\d+)$/)
    if (chapterDeleteMatch && method === "DELETE") {
      const chapterNumber = Number.parseInt(chapterDeleteMatch[1] ?? "", 10)
      const beforeCount = mockChapterList.chapters.length
      mockChapterList = {
        ...mockChapterList,
        chapters: mockChapterList.chapters.filter((item: typeof mockChapterList.chapters[number]) => item.number !== chapterNumber),
      }
      if (mockChapterList.chapters.length === beforeCount) {
        return notFound(route)
      }
      mockChapterList.read_upto = Math.max(0, ...mockChapterList.chapters.filter((item: typeof mockChapterList.chapters[number]) => item.read).map((item: typeof mockChapterList.chapters[number]) => item.number))
      mockChapterList.current_chapter = mockChapterList.read_upto
      mockWorkspaceTree = {
        ...mockWorkspaceTree,
        chapters: mockWorkspaceTree.chapters.filter((item: typeof mockWorkspaceTree.chapters[number]) => item.chapter_number !== chapterNumber),
        scene_groups: mockWorkspaceTree.scene_groups.filter((item: typeof mockWorkspaceTree.scene_groups[number]) => item.chapter_number !== chapterNumber),
      }
      mockManuscriptAnnotations = mockManuscriptAnnotations.filter((annotation: typeof mockManuscriptAnnotations[number]) => annotation.chapter_number !== chapterNumber)
      return route.fulfill({ status: 204 })
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

    if (path === "/api/v1/books/book-1/notes" && method === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>
      const saved = {
        id: body.note_id ? String(body.note_id) : `note-${mockNotes.length + 1}`,
        book_id: "book-1",
        book_title: "Sky of Ash",
        chapter_number: typeof body.chapter_number === "number" ? body.chapter_number : null,
        chapter_title: body.chapter_number === 2 ? "The Ember Gate" : null,
        title: body.title ? String(body.title) : null,
        body: String(body.body ?? ""),
        created_at: "2026-05-08T12:00:00Z",
        updated_at: "2026-05-08T12:00:00Z",
      }
      mockNotes = [saved, ...mockNotes.filter((note: typeof mockNotes[number]) => note.id !== saved.id)]
      return json(route, saved)
    }

    if (path === "/api/v1/books/book-1/notes/vault" && method === "GET") {
      return json(route, mockVaultNotes)
    }

    if (path === "/api/v1/books/book-1/notes/vault" && method === "PUT") {
      const body = route.request().postDataJSON() as Record<string, unknown>
      const pathValue = String(body.path ?? "")
      const saved = {
        id: `vault-note-${mockVaultNotes.length + 1}`,
        book_id: "book-1",
        path: pathValue,
        source: "manual_editor",
        content: String(body.content ?? ""),
        persisted: true,
        created_at: "2026-05-08T12:00:00Z",
        updated_at: "2026-05-08T12:00:00Z",
      }
      mockVaultNotes = [
        saved,
        ...mockVaultNotes.filter((note: typeof mockVaultNotes[number]) => note.path.toLowerCase() !== pathValue.toLowerCase()),
      ]
      return json(route, saved)
    }

    if (path === "/api/v1/reader/book-1/progress" && method === "GET") {
      return json(route, mockReadingProgress)
    }

    if (path === "/api/v1/reader/book-1/progress" && method === "PUT") {
      const currentChapter = Number.parseInt(url.searchParams.get("current_chapter") ?? "", 10)
      const scrollPct = Number.parseFloat(url.searchParams.get("scroll_pct") ?? "")
      if (Number.isFinite(currentChapter) && currentChapter > 0) {
        mockReadingProgress = {
          ...mockReadingProgress,
          current_chapter: currentChapter,
        }
      }
      if (Number.isFinite(scrollPct)) {
        mockReadingProgress = {
          ...mockReadingProgress,
          scroll_pct: scrollPct,
        }
      }
      return json(route, mockReadingProgress)
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
      return json(route, mockChapterList)
    }

    if (path === "/api/v1/reader/book-1/relationships" && method === "GET") {
      return json(route, mockRelationshipGraph)
    }

    if (path === "/api/v1/books/book-1/cover" && method === "GET") {
      return route.fulfill({
        status: 200,
        headers: {
          "content-type": "image/png",
        },
        body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAukB9VE3d2QAAAAASUVORK5CYII=", "base64"),
      })
    }

    const readerMediaMatch = path.match(/^\/api\/v1\/reader\/media\/([^/]+)$/)
    if (readerMediaMatch && method === "GET") {
      return route.fulfill({
        status: 200,
        headers: {
          "content-type": "image/png",
        },
        body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAukB9VE3d2QAAAAASUVORK5CYII=", "base64"),
      })
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
      if (voiceConsistencyMode === "backend-error") {
        return route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Voice review is temporarily unavailable." }),
        })
      }
      if (voiceConsistencyMode === "weak-attribution") {
        return json(route, weakAttributionVoiceConsistency)
      }
      if (voiceConsistencyMode === "selected-character") {
        return json(route, selectedCharacterVoiceConsistency)
      }
      const payload = route.request().postDataJSON() as { character_id?: string } | null
      if (payload?.character_id === "char-gregor") {
        return json(route, selectedCharacterVoiceConsistency)
      }
      if (payload?.character_id === "char-grete") {
        return json(route, weakAttributionVoiceConsistency)
      }
      return json(route, voiceConsistency)
    }

    if (path === "/api/v1/intelligence/book-1/world-building/documents" && method === "GET") {
      return json(route, worldBuildingDocuments)
    }

    if (path === "/api/v1/intelligence/book-1/world-building/bootstrap" && method === "GET") {
      return json(route, buildWorldBuildingBootstrap())
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
      const url = new URL(route.request().url())
      const page = Math.max(1, Number.parseInt(url.searchParams.get("page") || "1", 10) || 1)
      const pageSize = Math.max(1, Number.parseInt(url.searchParams.get("page_size") || "20", 10) || 20)
      const filteredPosts = filterForumFeedPosts(buildForumFeedPosts(), url.searchParams.get("q"))
      const pageItems = filteredPosts.slice((page - 1) * pageSize, page * pageSize)
      return json(route, {
        items: pageItems,
        total: filteredPosts.length,
        page,
        page_size: pageSize,
        has_more: page * pageSize < filteredPosts.length,
      })
    }

    if (path === "/api/v1/public/rankings/beta-novels" && method === "GET") {
      const url = new URL(route.request().url())
      const page = Math.max(1, Number.parseInt(url.searchParams.get("page") || "1", 10) || 1)
      const pageSize = Math.max(1, Number.parseInt(url.searchParams.get("page_size") || "20", 10) || 20)
      const ranking = url.searchParams.get("ranking") || "most_popular"
      const timeWindow = url.searchParams.get("time_window") || "monthly"
      const filteredPosts = filterForumFeedPosts(buildForumFeedPosts().filter((post) => post.thread_type === "novel"), url.searchParams.get("q"))
      const rankedPosts = filteredPosts.map((post, index) => ({
        ...post,
        ranking: {
          surface: "beta_novels",
          ranking_key: ranking,
          time_window: timeWindow,
          position: index + 1,
          score: post.discoverability_score,
          label: `${ranking.replaceAll("_", " ")} ${timeWindow}`.replace(/\b\w/g, (char) => char.toUpperCase()),
          supporting_note: "Mock ranking feed for local smoke coverage.",
          primary_timestamp: post.updated_at,
        },
      }))
      const pageItems = rankedPosts.slice((page - 1) * pageSize, page * pageSize)
      return json(route, {
        items: pageItems,
        total: rankedPosts.length,
        page,
        page_size: pageSize,
        has_more: page * pageSize < rankedPosts.length,
        ranking_key: ranking,
        time_window: timeWindow,
        surface: "beta_novels",
      })
    }

    if (path === "/api/v1/public/forum/my-posts" && method === "GET") {
      return json(route, publicForumPosts.filter((post) => post.author_user_id === "user-1"))
    }

    if (path === "/api/v1/public/forum/posts" && method === "POST") {
      const payload = route.request().postDataJSON() as {
        thread_type?: "novel" | "general"
        book_id?: string | null
        headline?: string
        body?: string
        desired_beta_reader_count?: number | null
        allow_contact_requests?: boolean
      } | null
      const threadType = payload?.thread_type ?? "novel"
      if (threadType === "novel" && payload?.book_id === "book-1" && publicForumPosts.some((post) => post.thread_type === "novel" && post.book_id === "book-1" && post.status === "open")) {
        return route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "This manuscript already has a beta forum post. Update it instead." }) })
      }
        const created: PublicForumPost = {
          id: `forum-post-${publicForumPosts.length + 1}`,
          thread_type: threadType,
          book_id: threadType === "novel" ? (payload?.book_id ?? "book-1") : null,
        author_user_id: "user-1",
        author_username: "author",
          author_reputation_score: 18,
          author_trust_level: "Trusted",
          title: threadType === "novel" ? book.title : null,
          author: threadType === "novel" ? book.author : null,
          genre: threadType === "novel" ? book.genre : null,
          description: threadType === "novel" ? book.public_description : null,
          work_type: threadType === "novel" ? "novel" : null,
        headline: payload?.headline ?? "",
        body: payload?.body ?? "",
        desired_beta_reader_count: threadType === "novel" ? (payload?.desired_beta_reader_count ?? null) : null,
        allow_contact_requests: threadType === "novel" ? Boolean(payload?.allow_contact_requests ?? true) : false,
        status: "open",
        viewer_interest_status: null,
        reaction: null,
        interest_count: 0,
        comment_count: 0,
        like_count: 0,
        dislike_count: 0,
        rating_summary: {
          average_rating: null,
          rating_count: 0,
          positive_rating_count: 0,
          neutral_rating_count: 0,
          negative_rating_count: 0,
        },
        discoverability_score: threadType === "novel" ? 42 : 8,
        created_at: "2026-05-14T13:00:00Z",
        updated_at: "2026-05-14T13:00:00Z",
      }
      publicForumPosts = [created, ...publicForumPosts]
      return json(route, created, 201)
    }

    const publicForumPostReactionMatch = path.match(/^\/api\/v1\/public\/forum\/posts\/([^/]+)\/reaction$/)
    if (publicForumPostReactionMatch && method === "PUT") {
      const payload = route.request().postDataJSON() as { reaction?: "like" | "dislike" | "clear" } | null
      const postId = publicForumPostReactionMatch[1]
      publicForumPosts = publicForumPosts.map((post) => {
        if (post.id !== postId) return post
        const previous = post.reaction
        const next = payload?.reaction === "clear" ? null : (payload?.reaction ?? null)
        return {
          ...post,
          reaction: next,
          like_count: previous === "like" && next !== "like" ? Math.max(0, post.like_count - 1) : previous !== "like" && next === "like" ? post.like_count + 1 : post.like_count,
          dislike_count: previous === "dislike" && next !== "dislike" ? Math.max(0, post.dislike_count - 1) : previous !== "dislike" && next === "dislike" ? post.dislike_count + 1 : post.dislike_count,
        }
      })
      const updated = publicForumPosts.find((post) => post.id === postId)
      return updated ? json(route, updated) : notFound(route)
    }

    if (path === "/api/v1/public/books" && method === "GET") {
      return json(route, publicBooks)
    }

    if (path === "/api/v1/public/analytics" && method === "GET") {
      return json(route, publicUploadsOverview)
    }

    if (path === "/api/v1/public/rankings/uploads" && method === "GET") {
      const url = new URL(route.request().url())
      const page = Math.max(1, Number.parseInt(url.searchParams.get("page") || "1", 10) || 1)
      const limit = Math.max(1, Number.parseInt(url.searchParams.get("limit") || "24", 10) || 24)
      const ranking = url.searchParams.get("ranking") || "most_popular"
      const timeWindow = url.searchParams.get("time_window") || "monthly"
      const search = (url.searchParams.get("search") || "").trim().toLowerCase()
      const filteredBooks = publicBooks.filter((book) => {
        if (!search) return true
        return [book.title, book.author, book.author_username, book.genre, book.description].join(" ").toLowerCase().includes(search)
      })
      const rankedBooks = filteredBooks.map((book, index) => ({
        ...book,
        ranking: {
          surface: "creator_uploads",
          ranking_key: ranking,
          time_window: timeWindow,
          position: index + 1,
          score: (book.analytics?.book_view_count ?? 0) + (book.analytics?.chapter_view_count ?? 0),
          label: `${ranking.replaceAll("_", " ")} ${timeWindow}`.replace(/\b\w/g, (char) => char.toUpperCase()),
          supporting_note: "Mock ranking feed for local smoke coverage.",
          primary_timestamp: book.published_at,
        },
      }))
      const pageItems = rankedBooks.slice((page - 1) * limit, page * limit)
      return json(route, {
        items: pageItems,
        total: rankedBooks.length,
        page,
        limit,
        has_more: page * limit < rankedBooks.length,
        ranking_key: ranking,
        time_window: timeWindow,
        surface: "creator_uploads",
      })
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

    const publicForumPostMatch = path.match(/^\/api\/v1\/public\/forum\/posts\/([^/]+)$/)
    if (publicForumPostMatch && method === "GET") {
      const post = publicForumPosts.find((item) => item.id === publicForumPostMatch[1])
      return post ? json(route, post) : notFound(route)
    }

    const publicForumCommentsMatch = path.match(/^\/api\/v1\/public\/forum\/posts\/([^/]+)\/comments$/)
    if (publicForumCommentsMatch && method === "GET") {
      const postId = publicForumCommentsMatch[1]
      return json(route, { items: buildNestedForumComments(postId) })
    }

    if (publicForumCommentsMatch && method === "POST") {
      const payload = route.request().postDataJSON() as { body?: string, parent_comment_id?: string | null } | null
      const postId = publicForumCommentsMatch[1]
      const post = publicForumPosts.find((item) => item.id === postId)
      if (!post) return notFound(route)
      if (payload?.parent_comment_id && !publicForumComments.some((comment) => comment.id === payload.parent_comment_id && comment.post_id === postId)) {
        return notFound(route)
      }
      const created = {
        id: `forum-comment-${publicForumComments.length + 1}`,
        post_id: postId,
        book_id: post.book_id,
        parent_comment_id: payload?.parent_comment_id ?? null,
        author_user_id: "user-1",
        author_username: "author",
        author_reputation_score: 18,
        author_trust_level: "Trusted",
        body: payload?.body ?? "",
        like_count: 0,
        dislike_count: 0,
        reaction: null,
        can_edit: true,
        replies: [],
        created_at: "2026-05-14T13:00:00Z",
        updated_at: "2026-05-14T13:00:00Z",
      }
      publicForumComments = [...publicForumComments, created]
      publicForumPosts = publicForumPosts.map((item) => item.id === postId ? { ...item, comment_count: countForumComments(postId) } : item)
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
