import { apiClient } from "./client"
import type { PublicBook, PublicBookDetail, PublicBookPage, PublicChapter } from "@/types/book"
import type {
  ContentReportPayload,
  ContentReportResponse,
  PublicUploadsOverview,
  PublicRankedBookListResponse,
  PublicForumComment,
  PublicForumCommentCursorPage,
  PublicForumInterest,
  PublicForumInterestCursorPage,
  PublicForumPost,
  PublicForumPostCursorPage,
  PublicForumPostListResponse,
  PublicUserProfile,
} from "@/types/public"
import { nestPublicForumComments } from "@/lib/utils/publicForum"

function appendOptionalForumField(formData: FormData, key: string, value: string | number | boolean | null | undefined) {
  if (value === null || typeof value === "undefined") return
  formData.append(key, String(value))
}

function forumPostFormData(payload: {
  threadType?: "novel" | "general"
  bookId?: string | null
  headline: string
  body: string
  desiredBetaReaderCount?: number | null
  allowContactRequests?: boolean
  status?: string
  removeImage?: boolean
  imageFile?: File | null
}) {
  const formData = new FormData()
  formData.append("thread_type", payload.threadType ?? "novel")
  appendOptionalForumField(formData, "book_id", payload.bookId)
  formData.append("headline", payload.headline)
  formData.append("body", payload.body)
  appendOptionalForumField(formData, "desired_beta_reader_count", payload.desiredBetaReaderCount)
  formData.append("allow_contact_requests", String(payload.allowContactRequests ?? true))
  appendOptionalForumField(formData, "status", payload.status)
  if (payload.removeImage) formData.append("remove_image", "true")
  if (payload.imageFile) formData.append("image", payload.imageFile)
  return formData
}

async function listAllPublicBookPages(options?: {
  contentSourceType?: string
  catalog?: string
  search?: string
  limit?: number
}): Promise<PublicBook[]> {
  const items: PublicBook[] = []
  let cursor: string | null = null
  const seen = new Set<string>()
  do {
    const page: PublicBookPage = await apiClient.get<PublicBookPage>("/public/books/page", {
      params: {
        ...(options?.contentSourceType ? { content_source_type: options.contentSourceType } : {}),
        ...(options?.catalog ? { catalog: options.catalog } : {}),
        ...(options?.search?.trim() ? { search: options.search.trim() } : {}),
        limit: options?.limit ?? 100,
        ...(cursor ? { cursor } : {}),
      },
    }).then((response) => response.data)
    items.push(...page.items)
    cursor = page.next_cursor
    if (cursor && seen.has(cursor)) break
    if (cursor) seen.add(cursor)
  } while (cursor)
  return items
}

export const publicApi = {
  listBooks: (options?: { contentSourceType?: string; catalog?: string; search?: string; page?: number; limit?: number }) =>
    listAllPublicBookPages(options),
  listBooksPage: (options?: {
    contentSourceType?: string
    catalog?: string
    search?: string
    cursor?: string | null
    limit?: number
  }) => apiClient.get<PublicBookPage>("/public/books/page", {
    params: {
      ...(options?.contentSourceType ? { content_source_type: options.contentSourceType } : {}),
      ...(options?.catalog ? { catalog: options.catalog } : {}),
      ...(options?.search?.trim() ? { search: options.search.trim() } : {}),
      ...(options?.cursor ? { cursor: options.cursor } : {}),
      ...(options?.limit ? { limit: options.limit } : {}),
    },
  }).then((response) => response.data),
  listSharedBooksPage: (options?: { cursor?: string | null; limit?: number }) =>
    apiClient.get<PublicBookPage>("/public/shared-books/page", {
      params: {
        ...(options?.cursor ? { cursor: options.cursor } : {}),
        ...(options?.limit ? { limit: options.limit } : {}),
      },
    }).then((response) => response.data),
  listCreatorUploads: (options?: { search?: string; page?: number; limit?: number }) =>
    listAllPublicBookPages({
      catalog: "creator_uploads",
      search: options?.search,
      limit: options?.limit,
    }),
  listRankedCreatorUploads: (options?: { ranking?: string; timeWindow?: string; search?: string; page?: number; limit?: number }) =>
    apiClient.get<PublicRankedBookListResponse>("/public/rankings/uploads", {
      params: {
        ranking: options?.ranking ?? "most_popular",
        time_window: options?.timeWindow ?? "monthly",
        ...(options?.search?.trim() ? { search: options.search.trim() } : {}),
        ...(options?.page ? { page: options.page } : {}),
        ...(options?.limit ? { limit: options.limit } : {}),
      },
    }).then((response) => response.data),
  getBook: (bookId: string) =>
    apiClient.get<PublicBookDetail>(`/public/books/${bookId}`).then((response) => response.data),
  getUploadsAnalytics: () =>
    apiClient.get<PublicUploadsOverview>("/public/analytics").then((response) => response.data),
  getChapter: (bookId: string, chapter: number) =>
    apiClient.get<PublicChapter>(`/public/books/${bookId}/chapter/${chapter}`).then((response) => response.data),
  trackView: (bookId: string, payload: { eventType: "book_view" | "chapter_view"; chapterNumber?: number }) =>
    apiClient.post<void>(`/public/books/${bookId}/analytics/view`, {
      event_type: payload.eventType,
      ...(typeof payload.chapterNumber === "number" ? { chapter_number: payload.chapterNumber } : {}),
    }).then(() => undefined),
  listForumPosts: (query?: string, page = 1, pageSize = 20, threadType?: "general" | "novel") =>
    apiClient.get<PublicForumPostListResponse>("/public/forum/posts", {
      params: {
        ...(query?.trim() ? { q: query.trim() } : {}),
        page,
        page_size: pageSize,
        ...(threadType ? { thread_type: threadType } : {}),
      },
    }).then((response) => response.data),
  listRankedBetaNovels: (options?: { ranking?: string; timeWindow?: string; query?: string; page?: number; pageSize?: number }) =>
    apiClient.get<PublicForumPostListResponse>("/public/rankings/beta-novels", {
      params: {
        ranking: options?.ranking ?? "most_popular",
        time_window: options?.timeWindow ?? "monthly",
        ...(options?.query?.trim() ? { q: options.query.trim() } : {}),
        page: options?.page ?? 1,
        page_size: options?.pageSize ?? 20,
      },
    }).then((response) => response.data),
  getForumPost: (postId: string) =>
    apiClient.get<PublicForumPost>(`/public/forum/posts/${postId}`).then((response) => response.data),
  listMyForumPostsPage: (cursor?: string | null, limit = 40) =>
    apiClient.get<PublicForumPostCursorPage>("/public/forum/my-posts/page", {
      params: { limit, ...(cursor ? { cursor } : {}) },
    }).then((response) => response.data),
  listMyForumPosts: () =>
    apiClient.get<PublicForumPostCursorPage>("/public/forum/my-posts/page", {
      params: { limit: 100 },
    }).then((response) => response.data.items),
  createForumPost: (payload: {
    threadType?: "novel" | "general"
    bookId?: string | null
    headline: string
    body: string
    desiredBetaReaderCount?: number | null
    allowContactRequests?: boolean
    imageFile?: File | null
  }) =>
    apiClient.post<PublicForumPost>(
      "/public/forum/posts",
      payload.imageFile
        ? forumPostFormData(payload)
        : {
            thread_type: payload.threadType ?? "novel",
            ...(payload.bookId ? { book_id: payload.bookId } : {}),
            headline: payload.headline,
            body: payload.body,
            desired_beta_reader_count: payload.desiredBetaReaderCount ?? null,
            allow_contact_requests: payload.allowContactRequests ?? true,
          },
    ).then((response) => response.data),
  updateForumPost: (postId: string, payload: {
    threadType?: "novel" | "general"
    headline: string
    body: string
    desiredBetaReaderCount?: number | null
    allowContactRequests?: boolean
    status?: string
    removeImage?: boolean
    imageFile?: File | null
  }) =>
    apiClient.put<PublicForumPost>(
      `/public/forum/posts/${postId}`,
      payload.imageFile
        ? forumPostFormData(payload)
        : {
            thread_type: payload.threadType ?? "novel",
            headline: payload.headline,
            body: payload.body,
            desired_beta_reader_count: payload.desiredBetaReaderCount ?? null,
            allow_contact_requests: payload.allowContactRequests ?? true,
            ...(payload.status ? { status: payload.status } : {}),
            ...(payload.removeImage ? { remove_image: true } : {}),
          },
    ).then((response) => response.data),
  listForumCommentsPage: (postId: string, cursor?: string | null, limit = 40) =>
    apiClient.get<PublicForumCommentCursorPage>(`/public/forum/posts/${postId}/comments/page`, {
      params: { limit, ...(cursor ? { cursor } : {}) },
    }).then((response) => response.data),
  listForumComments: (postId: string) =>
    apiClient.get<PublicForumCommentCursorPage>(`/public/forum/posts/${postId}/comments/page`, {
      params: { limit: 100 },
    }).then((response) => nestPublicForumComments(response.data.items)),
  listForumInterestsPage: (postId: string, cursor?: string | null, limit = 40) =>
    apiClient.get<PublicForumInterestCursorPage>(`/public/forum/posts/${postId}/interests/page`, {
      params: { limit, ...(cursor ? { cursor } : {}) },
    }).then((response) => response.data),
  listForumInterests: (postId: string) =>
    apiClient.get<PublicForumInterestCursorPage>(`/public/forum/posts/${postId}/interests/page`, {
      params: { limit: 100 },
    }).then((response) => response.data.items),
  createForumInterest: (postId: string, message: string) =>
    apiClient.post<PublicForumInterest>(`/public/forum/posts/${postId}/interests`, { message }).then((response) => response.data),
  createForumComment: (postId: string, body: string, parentCommentId?: string | null, imageFile?: File | null) => {
    const payload = imageFile ? new FormData() : null
    if (payload) {
      payload.append("body", body)
      if (parentCommentId) payload.append("parent_comment_id", parentCommentId)
      payload.append("image", imageFile as File)
    }
    return apiClient.post<PublicForumComment>(
      `/public/forum/posts/${postId}/comments`,
      payload ?? {
        body,
        ...(parentCommentId ? { parent_comment_id: parentCommentId } : {}),
      },
    ).then((response) => response.data)
  },
  reactToForumPost: (postId: string, reaction: "like" | "dislike" | "clear") =>
    apiClient.put<PublicForumPost>(`/public/forum/posts/${postId}/reaction`, { reaction }).then((response) => response.data),
  reactToForumComment: (commentId: string, reaction: "like" | "dislike" | "clear") =>
    apiClient.put<PublicForumComment>(`/public/forum/comments/${commentId}/reaction`, { reaction }).then((response) => response.data),
  getUserProfile: (username: string) =>
    apiClient.get<PublicUserProfile>(`/public/users/${encodeURIComponent(username)}`).then((response) => response.data),
  createContentReport: (payload: ContentReportPayload) =>
    apiClient.post<ContentReportResponse>("/reports/content", {
      book_id: payload.bookId,
      report_type: payload.reportType,
      reason: payload.reason,
      details: payload.details,
      reporter_email: payload.reporterEmail,
      copyright_owner_name: payload.copyrightOwnerName,
      copyright_work_description: payload.copyrightWorkDescription,
      copyright_original_url: payload.copyrightOriginalUrl,
      reported_content_url: payload.reportedContentUrl,
    }).then((response) => response.data),
}
