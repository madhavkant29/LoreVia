export interface PublicForumRatingSummary {
  average_rating: number | null
  rating_count: number
  positive_rating_count: number
  neutral_rating_count: number
  negative_rating_count: number
}

export interface PublicForumPost {
  id: string
  book_id: string
  author_user_id: string
  author_username: string | null
  author_reputation_score: number
  author_trust_level: string
  title: string
  author: string | null
  genre: string | null
  work_type: string
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
  created_at: string
}
