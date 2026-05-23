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
  AdvisorTaskStatusResponse,
  AdvisorAsyncAccepted,
  EditorialReviewResponse,
  InlineContinuityResponse,
  SeriesContinuityResponse,
  ManuscriptSynopsis,
  ContinuityReportFormat,
  ProseTightenResponse,
  WhatsTheWordResponse,
  VoiceConsistencyResponse,
} from "@/types/intelligence"

const MAX_ADVISOR_PASSAGE_CHARS = 12_000

function intelligencePath(bookId: string, suffix = "") {
  return `/intelligence/${normalizeBookRouteId(bookId)}${suffix}`
}

function clampAdvisorPassage(text: string) {
  return text.length > MAX_ADVISOR_PASSAGE_CHARS ? text.slice(0, MAX_ADVISOR_PASSAGE_CHARS) : text
}

async function pollAdvisorMessage(bookId: string, taskId: string): Promise<AdvisorResponse> {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const response = await apiClient.get<AdvisorTaskStatusResponse>(
      intelligencePath(bookId, `/advisor/message-async/${taskId}`),
    ).then(r => r.data)
    if (response.status === "complete" && response.result) {
      return response.result
    }
    if (response.status === "failed") {
      throw new Error(response.error || "Advisor generation failed")
    }
    await new Promise(resolve => globalThis.setTimeout(resolve, attempt < 10 ? 600 : 1000))
  }
  throw new Error("Advisor generation timed out")
}

async function pollSeriesAdvisorMessage(seriesId: string, taskId: string): Promise<AdvisorResponse> {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const response = await apiClient.get<AdvisorTaskStatusResponse>(
      `/intelligence/series/${seriesId}/advisor/message/${taskId}`,
    ).then(r => r.data)
    if (response.status === "complete" && response.result) {
      return response.result
    }
    if (response.status === "failed") {
      throw new Error(response.error || "Advisor generation failed")
    }
    await new Promise(resolve => globalThis.setTimeout(resolve, attempt < 10 ? 600 : 1000))
  }
  throw new Error("Advisor generation timed out")
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
    apiClient.post<AdvisorResponse | AdvisorAsyncAccepted>(intelligencePath(bookId, "/advisor/message-async"), {
      messages,
      total_chapters: totalChapters,
    }).then(async r => {
      const payload = r.data
      if ("reply" in payload) {
        return payload
      }
      return pollAdvisorMessage(bookId, payload.task_id)
    }),

  advisorSuggestions: (bookId: string) =>
    apiClient.get<AdvisorSuggestionsResponse>(intelligencePath(bookId, "/advisor/suggestions")).then(r => r.data),

  editorialReview: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<EditorialReviewResponse>(intelligencePath(bookId, "/advisor/editorial-review"), {
      text: clampAdvisorPassage(text),
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  proseTighten: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<ProseTightenResponse>(intelligencePath(bookId, "/advisor/prose-tighten"), {
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  whatsTheWord: (bookId: string, description: string, previousWord?: string | null) =>
    apiClient.post<WhatsTheWordResponse>(intelligencePath(bookId, "/advisor/whats-the-word"), {
      description,
      previous_word: previousWord ?? null,
    }).then(r => r.data),
  inlineContinuity: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<InlineContinuityResponse>(intelligencePath(bookId, "/advisor/inline-continuity"), {
      text: clampAdvisorPassage(text),
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  voiceConsistencyReview: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<VoiceConsistencyResponse>(intelligencePath(bookId, "/advisor/voice-consistency"), {
      text: clampAdvisorPassage(text),
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
    apiClient.post<AdvisorResponse | AdvisorAsyncAccepted>(`/intelligence/series/${seriesId}/advisor/message`, {
      messages,
    }).then(async r => {
      const payload = r.data
      if ("reply" in payload) {
        return payload
      }
      return pollSeriesAdvisorMessage(seriesId, payload.task_id)
    }),

  seriesContinuityCheck: (seriesId: string, bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<SeriesContinuityResponse>(`/intelligence/series/${seriesId}/continuity-check`, {
      book_id: normalizeBookRouteId(bookId),
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
}
