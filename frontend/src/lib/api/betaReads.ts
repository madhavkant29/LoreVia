import { apiClient } from "./client"
import { invalidateQueryKeys } from "@/lib/query/queryClient"

import type {
  BetaReadAssignment,
  BetaReadAssignmentDetail,
  BetaReadAssignmentListResponse,
  BetaReadQuestion,
} from "@/types/betaRead"

function invalidateBetaReadCache() {
  void invalidateQueryKeys("reader:beta-reads:")
  void invalidateQueryKeys("books:list:")
}

export const betaReadsApi = {
  createAssignment: (
    bookId: string,
    payload: {
      readerEmail: string
      taskLabel: string
      scopeKind?: string
      sectionLabel?: string | null
      chapterStart?: number | null
      chapterEnd?: number | null
      windowDays: number
      requiredProgressPct?: number
      requiredCommentCount?: number
      requiredFeedbackItemCount?: number
      requireFinalFeedback?: boolean
      authorQuestions?: string[]
    }
  ) =>
    apiClient.post<BetaReadAssignment>(`/books/${bookId}/beta-reads`, {
      reader_email: payload.readerEmail,
      task_label: payload.taskLabel,
      scope_kind: payload.scopeKind ?? "full_book",
      section_label: payload.sectionLabel,
      chapter_start: payload.chapterStart,
      chapter_end: payload.chapterEnd,
      window_days: payload.windowDays,
      required_progress_pct: payload.requiredProgressPct ?? 100,
      required_comment_count: payload.requiredCommentCount ?? 0,
      required_feedback_item_count: payload.requiredFeedbackItemCount ?? 1,
      require_final_feedback: payload.requireFinalFeedback ?? true,
      author_questions: payload.authorQuestions ?? [],
    }).then((response) => {
      invalidateBetaReadCache()
      return response.data
    }),
  listBookAssignments: (bookId: string) =>
    apiClient.get<BetaReadAssignmentListResponse>(`/books/${bookId}/beta-reads`).then((response) => response.data.items),
  getBookAssignmentDetail: (bookId: string, assignmentId: string) =>
    apiClient.get<BetaReadAssignmentDetail>(`/books/${bookId}/beta-reads/${assignmentId}`).then((response) => response.data),
  appendQuestions: (bookId: string, assignmentId: string, questions: string[]) =>
    apiClient.post<BetaReadQuestion[]>(`/books/${bookId}/beta-reads/${assignmentId}/questions`, {
      questions,
    }).then((response) => {
      invalidateBetaReadCache()
      return response.data
    }),
  revokeAssignment: (bookId: string, assignmentId: string) =>
    apiClient.post<BetaReadAssignment>(`/books/${bookId}/beta-reads/${assignmentId}/revoke`).then((response) => {
      invalidateBetaReadCache()
      return response.data
    }),
  listMine: (bucket?: string) =>
    apiClient.get<BetaReadAssignmentListResponse>("/beta-reads", {
      params: bucket ? { bucket } : undefined,
    }).then((response) => response.data.items),
  getMineDetail: (assignmentId: string) =>
    apiClient.get<BetaReadAssignmentDetail>(`/beta-reads/${assignmentId}`).then((response) => response.data),
  start: (assignmentId: string) =>
    apiClient.post<BetaReadAssignment>(`/beta-reads/${assignmentId}/start`).then((response) => {
      invalidateBetaReadCache()
      return response.data
    }),
  createFeedbackItem: (
    assignmentId: string,
    payload: {
      kind: string
      chapterNumber?: number | null
      sceneId?: string | null
      questionId?: string | null
      reaction?: string | null
      anchorText?: string | null
      body?: string | null
    }
  ) =>
    apiClient.post<BetaReadAssignmentDetail>(`/beta-reads/${assignmentId}/feedback-items`, {
      kind: payload.kind,
      chapter_number: payload.chapterNumber ?? null,
      scene_id: payload.sceneId ?? null,
      question_id: payload.questionId ?? null,
      reaction: payload.reaction ?? null,
      anchor_text: payload.anchorText ?? null,
      body: payload.body ?? null,
    }).then((response) => {
      invalidateBetaReadCache()
      return response.data
    }),
  deleteFeedbackItem: (assignmentId: string, feedbackItemId: string) =>
    apiClient.delete<BetaReadAssignmentDetail>(`/beta-reads/${assignmentId}/feedback-items/${feedbackItemId}`).then((response) => {
      invalidateBetaReadCache()
      return response.data
    }),
  updateBookFeedbackItem: (
    bookId: string,
    assignmentId: string,
    feedbackItemId: string,
    payload: {
      authorStatus: string
      authorTaskId?: string | null
    }
  ) =>
    apiClient.put<BetaReadAssignmentDetail>(`/books/${bookId}/beta-reads/${assignmentId}/feedback-items/${feedbackItemId}`, {
      author_status: payload.authorStatus,
      author_task_id: payload.authorTaskId ?? null,
    }).then((response) => {
      invalidateBetaReadCache()
      return response.data
    }),
  submitReview: (assignmentId: string, finalFeedback: string, finalRating: number) =>
    apiClient.post<BetaReadAssignment>(`/beta-reads/${assignmentId}/submit-feedback`, {
      final_feedback: finalFeedback,
      final_rating: finalRating,
    }).then((response) => {
      invalidateBetaReadCache()
      return response.data
    }),
}
