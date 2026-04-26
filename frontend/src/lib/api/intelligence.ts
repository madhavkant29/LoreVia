import { apiClient } from "./client"
import type {
  ChatMessage,
  CrossBookIntelligence,
  GroundedAnswer,
  AdvisorMessage,
  AdvisorResponse,
  AdvisorGreeting,
  AdvisorSuggestionsResponse,
  EditorialReviewResponse,
  ManuscriptSynopsis,
  ContinuityReportFormat,
  VoiceConsistencyResponse,
} from "@/types/intelligence"

export const intelligenceApi = {
  answer: (bookId: string, question: string, currentChapter: number) =>
    apiClient.post<GroundedAnswer>(`/intelligence/${bookId}/qa`, {
      question, current_chapter: currentChapter,
    }).then(r => r.data),

  chat: (bookId: string, characterId: string, messages: ChatMessage[], currentChapter: number, contextSummary = "") =>
    apiClient.post<{ reply: string; character: string; grounded_hint?: string | null }>(
      `/intelligence/${bookId}/chat/${characterId}`,
      { messages, current_chapter: currentChapter, context_summary: contextSummary }
    ).then(r => r.data),

  getCrossBookIntelligence: (bookId: string) =>
    apiClient.get<CrossBookIntelligence>(`/intelligence/${bookId}/cross-book-intelligence`).then(r => r.data),

  // Story Advisor
  advisorGreeting: (bookId: string) =>
    apiClient.get<AdvisorGreeting>(`/intelligence/${bookId}/advisor/greeting`).then(r => r.data),

  advisorMessage: (bookId: string, messages: AdvisorMessage[], totalChapters: number) =>
    apiClient.post<AdvisorResponse>(`/intelligence/${bookId}/advisor/message`, {
      messages,
      total_chapters: totalChapters,
    }).then(r => r.data),

  advisorSuggestions: (bookId: string) =>
    apiClient.get<AdvisorSuggestionsResponse>(`/intelligence/${bookId}/advisor/suggestions`).then(r => r.data),

  editorialReview: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<EditorialReviewResponse>(`/intelligence/${bookId}/advisor/editorial-review`, {
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  voiceConsistencyReview: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<VoiceConsistencyResponse>(`/intelligence/${bookId}/advisor/voice-consistency`, {
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  continuityReport: (bookId: string, text: string, format: ContinuityReportFormat, chapterNum?: number) =>
    apiClient.get<Blob>(`/intelligence/${bookId}/advisor/continuity-report`, {
      params: { text, format, chapter_num: chapterNum ?? null },
      responseType: "blob",
    }).then(r => r.data),
  synopsis: (bookId: string, spoilerLevel: "minimal" | "none" = "minimal") =>
    apiClient.get<ManuscriptSynopsis>(`/intelligence/${bookId}/advisor/synopsis`, {
      params: { spoiler_level: spoilerLevel },
    }).then(r => r.data),

  // Series-wide operations
  seriesAdvisorMessage: (seriesId: string, messages: AdvisorMessage[]) =>
    apiClient.post<AdvisorResponse>(`/intelligence/series/${seriesId}/advisor/message`, {
      messages,
    }).then(r => r.data),

  seriesContinuityCheck: (seriesId: string, bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<EditorialReviewResponse>(`/intelligence/series/${seriesId}/continuity-check`, {
      book_id: bookId,
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
}
