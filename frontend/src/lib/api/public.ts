import { apiClient } from "./client"
import type { PublicBook, PublicBookDetail, PublicChapter } from "@/types/book"
import type { PublicForumComment, PublicForumCommentListResponse, PublicForumPost, PublicForumPostListResponse, PublicUserProfile } from "@/types/public"

export const publicApi = {
  listBooks: () => apiClient.get<PublicBook[]>("/public/books").then((response) => response.data),
  getBook: (bookId: string) =>
    apiClient.get<PublicBookDetail>(`/public/books/${bookId}`).then((response) => response.data),
  getChapter: (bookId: string, chapter: number) =>
    apiClient.get<PublicChapter>(`/public/books/${bookId}/chapter/${chapter}`).then((response) => response.data),
  listForumPosts: (query?: string) =>
    apiClient.get<PublicForumPostListResponse>("/public/forum/posts", {
      params: query?.trim() ? { q: query.trim() } : undefined,
    }).then((response) => response.data.items),
  getForumPost: (postId: string) =>
    apiClient.get<PublicForumPost>(`/public/forum/posts/${postId}`).then((response) => response.data),
  listForumComments: (postId: string) =>
    apiClient.get<PublicForumCommentListResponse>(`/public/forum/posts/${postId}/comments`).then((response) => response.data.items),
  createForumComment: (postId: string, body: string) =>
    apiClient.post<PublicForumComment>(`/public/forum/posts/${postId}/comments`, { body }).then((response) => response.data),
  reactToForumComment: (commentId: string, reaction: "like" | "dislike" | "clear") =>
    apiClient.put<PublicForumComment>(`/public/forum/comments/${commentId}/reaction`, { reaction }).then((response) => response.data),
  getUserProfile: (username: string) =>
    apiClient.get<PublicUserProfile>(`/public/users/${encodeURIComponent(username)}`).then((response) => response.data),
}
