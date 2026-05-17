import type { Book } from "@/types/book"
import type { PublicForumPost } from "@/types/public"

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

export function isEligibleForumAuthorBook(book: Book): boolean {
  if (book.mode !== "author" || Boolean(book.hidden_at) || Boolean(book.archived_at)) {
    return false
  }
  if (!book.is_public) {
    return true
  }
  return book.source_kind === "user_public_share" && (book.public_share_status === "approved" || !book.public_share_status)
}

export function getEligibleForumAuthorBooks(books: Book[], myForumPosts: PublicForumPost[]): Book[] {
  const openDiscussionBookIds = new Set(
    myForumPosts
      .filter((post) => post.status === "open")
      .map((post) => post.book_id),
  )

  return books.filter((book) => isEligibleForumAuthorBook(book) && !openDiscussionBookIds.has(book.id))
}
