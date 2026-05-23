import { apiClient } from "./client"
import type { PublicBook, PublicBookDetail, PublicChapter } from "@/types/book"
import type {
  ContentReportPayload,
  ContentReportResponse,
  PublicUploadsOverview,
  PublicForumComment,
  PublicForumCommentListResponse,
  PublicForumInterest,
  PublicForumInterestListResponse,
  PublicForumPost,
  PublicForumPostListResponse,
  PublicUserProfile,
} from "@/types/public"

export const publicApi = {
  listBooks: (options?: { contentSourceType?: string; catalog?: string; search?: string; page?: number; limit?: number }) =>
    apiClient.get<PublicBook[]>("/public/books", {
      params: {
        ...(options?.contentSourceType ? { content_source_type: options.contentSourceType } : {}),
        ...(options?.catalog ? { catalog: options.catalog } : {}),
        ...(options?.search?.trim() ? { search: options.search.trim() } : {}),
        ...(options?.page ? { page: options.page } : {}),
        ...(options?.limit ? { limit: options.limit } : {}),
      },
    }).then((response) => response.data),
  listCreatorUploads: (options?: { search?: string; page?: number; limit?: number }) =>
    apiClient.get<PublicBook[]>("/public/uploads", {
      params: {
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
  listForumPosts: (query?: string, page = 1, pageSize = 20) =>
    apiClient.get<PublicForumPostListResponse>("/public/forum/posts", {
      params: {
        ...(query?.trim() ? { q: query.trim() } : {}),
        page,
        page_size: pageSize,
      },
    }).then((response) => response.data),
  getForumPost: (postId: string) =>
    apiClient.get<PublicForumPost>(`/public/forum/posts/${postId}`).then((response) => response.data),
  listMyForumPosts: () =>
    apiClient.get<PublicForumPost[]>("/public/forum/my-posts").then((response) => response.data),
  createForumPost: (payload: {
    threadType?: "novel" | "general"
    bookId?: string | null
    headline: string
    body: string
    desiredBetaReaderCount?: number | null
    allowContactRequests?: boolean
  }) =>
    apiClient.post<PublicForumPost>("/public/forum/posts", {
      thread_type: payload.threadType ?? "novel",
      ...(payload.bookId ? { book_id: payload.bookId } : {}),
      headline: payload.headline,
      body: payload.body,
      desired_beta_reader_count: payload.desiredBetaReaderCount ?? null,
      allow_contact_requests: payload.allowContactRequests ?? true,
    }).then((response) => response.data),
  updateForumPost: (postId: string, payload: {
    threadType?: "novel" | "general"
    headline: string
    body: string
    desiredBetaReaderCount?: number | null
    allowContactRequests?: boolean
    status?: string
  }) =>
    apiClient.put<PublicForumPost>(`/public/forum/posts/${postId}`, {
      thread_type: payload.threadType ?? "novel",
      headline: payload.headline,
      body: payload.body,
      desired_beta_reader_count: payload.desiredBetaReaderCount ?? null,
      allow_contact_requests: payload.allowContactRequests ?? true,
      ...(payload.status ? { status: payload.status } : {}),
    }).then((response) => response.data),
  listForumComments: (postId: string) =>
    apiClient.get<PublicForumCommentListResponse>(`/public/forum/posts/${postId}/comments`).then((response) => response.data.items),
  listForumInterests: (postId: string) =>
    apiClient.get<PublicForumInterestListResponse>(`/public/forum/posts/${postId}/interests`).then((response) => response.data.items),
  createForumInterest: (postId: string, message: string) =>
    apiClient.post<PublicForumInterest>(`/public/forum/posts/${postId}/interests`, { message }).then((response) => response.data),
  createForumComment: (postId: string, body: string, parentCommentId?: string | null) =>
    apiClient.post<PublicForumComment>(`/public/forum/posts/${postId}/comments`, {
      body,
      ...(parentCommentId ? { parent_comment_id: parentCommentId } : {}),
    }).then((response) => response.data),
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
