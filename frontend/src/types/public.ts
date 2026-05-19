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
  work_type: string | null
  headline: string
  body: string
  desired_beta_reader_count: number | null
  allow_contact_requests: boolean
  status: string
  viewer_interest_status: string | null
  interest_count: number
  comment_count: number
  rating_summary: PublicForumRatingSummary
  discoverability_score: number
  created_at: string
  updated_at: string
}

export interface PublicForumComment {
  id: string
  post_id: string
  book_id: string | null
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
}

export interface PublicForumCommentListResponse {
  items: PublicForumComment[]
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

export interface PublicForumPostListResponse {
  items: PublicForumPost[]
  total: number
  page: number
  page_size: number
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

export interface PublicUserActivityPost {
  id: string
  thread_type: "novel" | "general" | string
  status: string
  headline: string
  body: string
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
