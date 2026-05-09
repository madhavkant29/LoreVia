import { apiClient } from "./client"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type {
  ChatMessage,
  CrossBookIntelligence,
  GroundedAnswer,
  AdvisorMessage,
  AdvisorResponse,
  AdvisorGreeting,
  AdvisorSuggestionsResponse,
  EditorialReviewResponse,
  InlineContinuityResponse,
  SeriesContinuityResponse,
  ManuscriptSynopsis,
  ContinuityReportFormat,
  ProseTightenResponse,
  VoiceConsistencyResponse,
} from "@/types/intelligence"

function intelligencePath(bookId: string, suffix = "") {
  return `/intelligence/${normalizeBookRouteId(bookId)}${suffix}`
}

export const intelligenceApi = {
  answer: (bookId: string, question: string, currentChapter: number) =>
    apiClient.post<GroundedAnswer>(intelligencePath(bookId, "/qa"), {
      question, current_chapter: currentChapter,
    }).then(r => r.data),

  chat: (bookId: string, characterId: string, messages: ChatMessage[], currentChapter: number, contextSummary = "") =>
    apiClient.post<{ reply: string; character: string; grounded_hint?: string | null }>(
      intelligencePath(bookId, `/chat/${characterId}`),
      { messages, current_chapter: currentChapter, context_summary: contextSummary }
    ).then(r => r.data),

  getCrossBookIntelligence: (bookId: string) =>
    apiClient.get<CrossBookIntelligence>(intelligencePath(bookId, "/cross-book-intelligence")).then(r => r.data),

  // Story Advisor
  advisorGreeting: (bookId: string) =>
    apiClient.get<AdvisorGreeting>(intelligencePath(bookId, "/advisor/greeting")).then(r => r.data),

  advisorMessage: (bookId: string, messages: AdvisorMessage[], totalChapters: number) =>
    apiClient.post<AdvisorResponse>(intelligencePath(bookId, "/advisor/message"), {
      messages,
      total_chapters: totalChapters,
    }).then(r => r.data),

  advisorSuggestions: (bookId: string) =>
    apiClient.get<AdvisorSuggestionsResponse>(intelligencePath(bookId, "/advisor/suggestions")).then(r => r.data),

  editorialReview: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<EditorialReviewResponse>(intelligencePath(bookId, "/advisor/editorial-review"), {
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  proseTighten: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<ProseTightenResponse>(intelligencePath(bookId, "/advisor/prose-tighten"), {
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  inlineContinuity: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<InlineContinuityResponse>(intelligencePath(bookId, "/advisor/inline-continuity"), {
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  voiceConsistencyReview: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<VoiceConsistencyResponse>(intelligencePath(bookId, "/advisor/voice-consistency"), {
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  continuityReport: (bookId: string, text: string, format: ContinuityReportFormat, chapterNum?: number) =>
    apiClient.get<Blob>(intelligencePath(bookId, "/advisor/continuity-report"), {
      params: { text, format, chapter_num: chapterNum ?? null },
      responseType: "blob",
    }).then(r => r.data),
  synopsis: (bookId: string, spoilerLevel: "minimal" | "none" = "minimal") =>
    apiClient.get<ManuscriptSynopsis>(intelligencePath(bookId, "/advisor/synopsis"), {
      params: { spoiler_level: spoilerLevel },
    }).then(r => r.data),

  // Series-wide operations
  seriesAdvisorMessage: (seriesId: string, messages: AdvisorMessage[]) =>
    apiClient.post<AdvisorResponse>(`/intelligence/series/${seriesId}/advisor/message`, {
      messages,
    }).then(r => r.data),

  seriesContinuityCheck: (seriesId: string, bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<SeriesContinuityResponse>(`/intelligence/series/${seriesId}/continuity-check`, {
      book_id: normalizeBookRouteId(bookId),
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
}
