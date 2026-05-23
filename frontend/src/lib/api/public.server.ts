import "server-only"

import { notFound } from "next/navigation"

import { resolveApiOrigin } from "@/lib/constants"
import type { PublicBook, PublicBookDetail, PublicChapter } from "@/types/book"
import type { PublicForumComment, PublicForumPost, PublicForumPostListResponse, PublicUploadsOverview, PublicUserProfile } from "@/types/public"

const PUBLIC_API_BASE = `${resolveApiOrigin()}/api/v1/public`

async function fetchPublicJson<T>(path: string, revalidate = 300): Promise<T> {
  const response = await fetch(`${PUBLIC_API_BASE}${path}`, {
    next: { revalidate },
  })

  if (response.status === 404) {
    notFound()
  }

  if (!response.ok) {
    throw new Error(`Public API request failed for ${path} with status ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function listPublicBooksServer(): Promise<PublicBook[]> {
  return fetchPublicJson<PublicBook[]>("/books")
}

export function listCreatorPublicUploadsServer(query?: string): Promise<PublicBook[]> {
  const searchParams = new URLSearchParams()
  if (query?.trim()) {
    searchParams.set("search", query.trim())
  }
  const suffix = searchParams.toString()
  return fetchPublicJson<PublicBook[]>(`/uploads${suffix ? `?${suffix}` : ""}`)
}

export function getPublicBookServer(bookId: string): Promise<PublicBookDetail> {
  return fetchPublicJson<PublicBookDetail>(`/books/${encodeURIComponent(bookId)}`)
}

export function getPublicUploadsAnalyticsServer(): Promise<PublicUploadsOverview> {
  return fetchPublicJson<PublicUploadsOverview>("/analytics", 120)
}

export function getPublicChapterServer(bookId: string, chapterNumber: number): Promise<PublicChapter> {
  return fetchPublicJson<PublicChapter>(`/books/${encodeURIComponent(bookId)}/chapter/${chapterNumber}`)
}

export function listPublicForumPostsServer(query?: string): Promise<PublicForumPostListResponse> {
  const searchParams = new URLSearchParams()
  if (query?.trim()) {
    searchParams.set("q", query.trim())
  }
  const suffix = searchParams.toString()
  return fetchPublicJson<PublicForumPostListResponse>(`/forum/posts${suffix ? `?${suffix}` : ""}`, 120)
}

export function getPublicForumPostServer(postId: string): Promise<PublicForumPost> {
  return fetchPublicJson<PublicForumPost>(`/forum/posts/${encodeURIComponent(postId)}`, 120)
}

export function listPublicForumCommentsServer(postId: string): Promise<PublicForumComment[]> {
  return fetchPublicJson<PublicForumComment[]>(`/forum/posts/${encodeURIComponent(postId)}/comments`, 120)
}

export function getPublicUserProfileServer(username: string): Promise<PublicUserProfile> {
  return fetchPublicJson<PublicUserProfile>(`/users/${encodeURIComponent(username)}`)
}
