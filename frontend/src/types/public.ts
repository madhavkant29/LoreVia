export interface PublicRankingMetadata {
  surface: string
  ranking_key: string
  time_window: string
  position: number | null
  score: number | null
  label: string | null
  supporting_note: string | null
  primary_timestamp: string | null
}

export interface PublicForumRatingSummary {
  average_rating: number | null
  rating_count: number
  positive_rating_count: number
  neutral_rating_count: number
  negative_rating_count: number
}

export interface PublicForumPost {
  id: string
  thread_type: "novel" | "general" | string
  book_id: string | null
  author_user_id: string
  author_username: string | null
  author_reputation_score: number
  author_trust_level: string
  title: string | null
  author: string | null
  genre: string | null
  description: string | null
  work_type: string | null
  headline: string
  body: string
  image_url?: string | null
  image_filename?: string | null
  image_content_type?: string | null
  desired_beta_reader_count: number | null
  allow_contact_requests: boolean
  status: string
  viewer_interest_status: string | null
  reaction: "like" | "dislike" | null
  interest_count: number
  comment_count: number
  like_count: number
  dislike_count: number
  rating_summary: PublicForumRatingSummary
  discoverability_score: number
  ranking?: PublicRankingMetadata | null
  created_at: string
  updated_at: string
}

export interface PublicForumComment {
  id: string
  post_id: string
  book_id: string | null
  parent_comment_id: string | null
  author_user_id: string
  author_username: string | null
  author_reputation_score: number
  author_trust_level: string
  body: string
  image_url?: string | null
  image_filename?: string | null
  image_content_type?: string | null
  like_count: number
  dislike_count: number
  reaction: "like" | "dislike" | null
  can_edit: boolean
  replies: PublicForumComment[]
  created_at: string
  updated_at: string
}

export interface PublicForumCommentListResponse {
  items: PublicForumComment[]
}

export interface PublicForumCommentCursorPage {
  items: PublicForumComment[]
  next_cursor: string | null
  has_more: boolean
}

export interface PublicForumInterest {
  id: string
  post_id: string
  book_id: string
  author_user_id: string
  interested_user_id: string
  interested_username: string | null
  interested_email: string
  message: string
  status: string
  created_at: string
  updated_at: string
}

export interface PublicForumInterestListResponse {
  items: PublicForumInterest[]
}

export interface PublicForumInterestCursorPage {
  items: PublicForumInterest[]
  next_cursor: string | null
  has_more: boolean
}

export interface PublicForumPostListResponse {
  items: PublicForumPost[]
  total: number
  page: number
  page_size: number
  has_more: boolean
  ranking_key?: string | null
  time_window?: string | null
  surface?: string | null
}

export interface PublicForumPostCursorPage {
  items: PublicForumPost[]
  next_cursor: string | null
  has_more: boolean
}

export interface PublicUserProject {
  book_id: string
  title: string
  genre: string | null
  description: string | null
  progress_words: number
  source: "forum" | "public_book"
  forum_post_id: string | null
  public_book_id: string | null
}

export interface PublicBookAnalytics {
  book_view_count: number
  unique_reader_count_30d: number
  chapter_view_count: number
  published_at: string | null
  chapter_count: number
  total_words: number
  has_open_discussion: boolean
  open_discussion_count: number
  discussion_comment_count: number
  discussion_interest_count: number
}

export interface PublicAuthorAnalytics {
  total_book_views: number
  total_unique_readers_30d: number
  total_chapter_views: number
  total_public_books: number
  total_chapters: number
  total_words: number
  latest_published_at: string | null
  open_forum_discussions_count: number
}

export interface PublicUploadsBreakdownEntry {
  key: string
  label: string
  count: number
}

export interface PublicUploadsOverview {
  total_public_books: number
  total_authors: number
  total_visible_chapters: number
  total_visible_words: number
  uploads_last_30_days: number
  genre_breakdown: PublicUploadsBreakdownEntry[]
  work_type_breakdown: PublicUploadsBreakdownEntry[]
  recent_uploads: import("./book").PublicBook[]
}

export interface PublicRankedBookListResponse {
  items: import("./book").PublicBook[]
  total: number
  page: number
  limit: number
  has_more: boolean
  ranking_key: string
  time_window: string
  surface: string
}

export interface PublicUserActivityPost {
  id: string
  thread_type: "novel" | "general" | string
  status: string
  headline: string
  body: string
  image_url?: string | null
  image_filename?: string | null
  image_content_type?: string | null
  title: string | null
  genre: string | null
  work_type: string | null
  book_id: string | null
  comment_count: number
  interest_count: number
  like_count: number
  dislike_count: number
  created_at: string
  updated_at: string
}

export interface PublicUserActivityComment {
  id: string
  post_id: string
  thread_type: "novel" | "general" | string
  post_status: string
  post_headline: string
  post_title: string | null
  book_id: string | null
  body: string
  image_url?: string | null
  image_filename?: string | null
  image_content_type?: string | null
  like_count: number
  dislike_count: number
  created_at: string
  updated_at: string
}

export interface PublicUserProfile {
  user_id: string
  username: string
  reputation_score: number
  reputation_likes_received: number
  reputation_dislikes_received: number
  trust_level: string
  forum_post_count: number
  forum_comment_count: number
  current_project: PublicUserProject | null
  public_books_count: number
  public_books: import("./book").PublicBook[]
  public_analytics: PublicAuthorAnalytics
  posts: PublicUserActivityPost[]
  comments: PublicUserActivityComment[]
  created_at: string
}

export interface ContentReportPayload {
  bookId: string
  reportType: "copyright" | "plagiarism" | "impersonation" | "spam" | "illegal_content" | "harassment" | "other"
  reason: string
  details?: string
  reporterEmail?: string
  copyrightOwnerName?: string
  copyrightWorkDescription?: string
  copyrightOriginalUrl?: string
  reportedContentUrl?: string
}

export interface ContentReportResponse {
  id: string
  status: string
  report_type: string
  reported_book_id: string
  created_at: string
  message?: string | null
}
