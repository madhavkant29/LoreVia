import type { Book } from "@/types/book"
import type { PublicForumComment, PublicForumPost } from "@/types/public"

export function nestPublicForumComments(items: PublicForumComment[]): PublicForumComment[] {
  const byId = new Map(
    items.map((comment) => [comment.id, { ...comment, replies: [] as PublicForumComment[] }]),
  )
  const roots: PublicForumComment[] = []
  for (const item of items) {
    const comment = byId.get(item.id)
    if (!comment) continue
    const parent = item.parent_comment_id ? byId.get(item.parent_comment_id) : null
    if (parent) {
      parent.replies.push(comment)
    } else {
      roots.push(comment)
    }
  }
  return roots
}

type ForumAuthorBook = Pick<
  Book,
  | "id"
  | "mode"
  | "hidden_at"
  | "archived_at"
  | "is_public"
  | "source_kind"
  | "public_share_status"
  | "access_class"
>

export function formatReputationScore(score: number): string {
  const value = Number.isFinite(score) ? Math.trunc(score) : 0
  return value > 0 ? `+${value}` : String(value)
}

export function formatWordProgress(words: number): string {
  const value = Math.max(0, Math.trunc(words || 0))
  if (value >= 1000) {
    const compact = value / 1000
    return `${Number.isInteger(compact) ? compact.toFixed(0) : compact.toFixed(1)}k words`
  }
  return `${value} words`
}

export function isEligibleForumAuthorBook(book: ForumAuthorBook): boolean {
  if (
    (book.access_class != null && book.access_class !== "owner")
    || book.mode !== "author"
    || Boolean(book.hidden_at)
    || Boolean(book.archived_at)
  ) {
    return false
  }
  if (!book.is_public) {
    return true
  }
  return book.source_kind === "user_public_share" && (book.public_share_status === "approved" || !book.public_share_status)
}

export function getEligibleForumAuthorBooks<T extends ForumAuthorBook>(
  books: T[],
  myForumPosts: PublicForumPost[],
): T[] {
  const openDiscussionBookIds = new Set(
    myForumPosts
      .filter((post) => post.status === "open" && (post.thread_type || "novel") === "novel" && post.book_id)
      .map((post) => post.book_id),
  )

  return books.filter((book) => isEligibleForumAuthorBook(book) && !openDiscussionBookIds.has(book.id))
}
