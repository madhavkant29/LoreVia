import "server-only"

import { notFound } from "next/navigation"

import { resolveApiOrigin } from "@/lib/constants"
import type { PublicBook, PublicBookDetail, PublicBookPage, PublicChapter } from "@/types/book"
import type { PublicForumComment, PublicForumCommentCursorPage, PublicForumPost, PublicForumPostListResponse, PublicRankedBookListResponse, PublicUploadsOverview, PublicUserProfile } from "@/types/public"
import { nestPublicForumComments } from "@/lib/utils/publicForum"

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

export async function listPublicBooksServer(): Promise<PublicBook[]> {
  const items: PublicBook[] = []
  let cursor: string | null = null
  const seen = new Set<string>()
  do {
    const suffix: string = cursor
      ? `?limit=100&cursor=${encodeURIComponent(cursor)}`
      : "?limit=100"
    const page: PublicBookPage = await fetchPublicJson<PublicBookPage>(`/books/page${suffix}`)
    items.push(...page.items)
    cursor = page.next_cursor
    if (cursor && seen.has(cursor)) break
    if (cursor) seen.add(cursor)
  } while (cursor)
  return items
}

export function listPublicBooksPageServer(options?: {
  catalog?: string
  search?: string
  cursor?: string | null
  limit?: number
}): Promise<PublicBookPage> {
  const searchParams = new URLSearchParams()
  if (options?.catalog) searchParams.set("catalog", options.catalog)
  if (options?.search?.trim()) searchParams.set("search", options.search.trim())
  if (options?.cursor) searchParams.set("cursor", options.cursor)
  if (options?.limit) searchParams.set("limit", String(options.limit))
  const suffix = searchParams.toString()
  return fetchPublicJson<PublicBookPage>(`/books/page${suffix ? `?${suffix}` : ""}`)
}

export async function listCreatorPublicUploadsServer(query?: string): Promise<PublicBook[]> {
  const searchParams = new URLSearchParams()
  if (query?.trim()) {
    searchParams.set("search", query.trim())
  }
  const items: PublicBook[] = []
  let cursor: string | null = null
  const seen = new Set<string>()
  do {
    const pageParams = new URLSearchParams(searchParams)
    pageParams.set("catalog", "creator_uploads")
    pageParams.set("limit", "100")
    if (cursor) pageParams.set("cursor", cursor)
    const page: PublicBookPage = await fetchPublicJson<PublicBookPage>(
      `/books/page?${pageParams.toString()}`,
    )
    items.push(...page.items)
    cursor = page.next_cursor
    if (cursor && seen.has(cursor)) break
    if (cursor) seen.add(cursor)
  } while (cursor)
  return items
}

export function listRankedCreatorPublicUploadsServer(options?: {
  ranking?: string
  timeWindow?: string
  query?: string
  page?: number
  limit?: number
}): Promise<PublicRankedBookListResponse> {
  const searchParams = new URLSearchParams()
  searchParams.set("ranking", options?.ranking ?? "most_popular")
  searchParams.set("time_window", options?.timeWindow ?? "monthly")
  if (options?.query?.trim()) {
    searchParams.set("search", options.query.trim())
  }
  if (options?.page) {
    searchParams.set("page", String(options.page))
  }
  if (options?.limit) {
    searchParams.set("limit", String(options.limit))
  }
  return fetchPublicJson<PublicRankedBookListResponse>(`/rankings/uploads?${searchParams.toString()}`, 120)
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

export function listRankedBetaNovelsServer(options?: {
  ranking?: string
  timeWindow?: string
  query?: string
  page?: number
  pageSize?: number
}): Promise<PublicForumPostListResponse> {
  const searchParams = new URLSearchParams()
  searchParams.set("ranking", options?.ranking ?? "most_popular")
  searchParams.set("time_window", options?.timeWindow ?? "monthly")
  searchParams.set("page", String(options?.page ?? 1))
  searchParams.set("page_size", String(options?.pageSize ?? 20))
  if (options?.query?.trim()) {
    searchParams.set("q", options.query.trim())
  }
  return fetchPublicJson<PublicForumPostListResponse>(`/rankings/beta-novels?${searchParams.toString()}`, 120)
}

export function getPublicForumPostServer(postId: string): Promise<PublicForumPost> {
  return fetchPublicJson<PublicForumPost>(`/forum/posts/${encodeURIComponent(postId)}`, 120)
}

export function listPublicForumCommentsServer(postId: string): Promise<PublicForumComment[]> {
  return listPublicForumCommentsPageServer(postId, 100).then((data) => data.items)
}

export function listPublicForumCommentsPageServer(
  postId: string,
  limit = 40,
): Promise<PublicForumCommentCursorPage> {
  return fetchPublicJson<PublicForumCommentCursorPage>(
    `/forum/posts/${encodeURIComponent(postId)}/comments/page?limit=${limit}`,
    120,
  ).then((data) => ({ ...data, items: nestPublicForumComments(data.items) }))
}

export function getPublicUserProfileServer(username: string): Promise<PublicUserProfile> {
  return fetchPublicJson<PublicUserProfile>(`/users/${encodeURIComponent(username)}`)
}
