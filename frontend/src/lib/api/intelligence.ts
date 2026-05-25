import { apiClient } from "./client"
import { API_BASE } from "@/lib/constants"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type {
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

type AdvisorStreamHandlers = {
  onDelta?: (content: string) => void
  onStage?: (message: string) => void
  signal?: AbortSignal
}

function intelligencePath(bookId: string, suffix = "") {
  return `/intelligence/${normalizeBookRouteId(bookId)}${suffix}`
}

function clampAdvisorPassage(text: string) {
  return text.length > MAX_ADVISOR_PASSAGE_CHARS ? text.slice(0, MAX_ADVISOR_PASSAGE_CHARS) : text
}

async function requestSse<T>(
  path: string,
  options: {
    method?: "GET" | "POST"
    payload?: Record<string, unknown>
  } = {},
  handlers: AdvisorStreamHandlers = {},
  retried = false,
): Promise<T> {
  const method = options.method ?? "POST"
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    credentials: "include",
    body: method === "POST" ? JSON.stringify(options.payload ?? {}) : undefined,
    signal: handlers.signal,
  })

  if (response.status === 401 && !retried) {
    await apiClient.post("/auth/refresh")
    return requestSse<T>(path, options, handlers, true)
  }

  if (!response.ok) {
    throw new Error(`${response.status}: Advisor stream failed`)
  }
  if (!response.body) {
    throw new Error("Advisor stream is unavailable in this browser")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let finalPayload: T | null = null

  const processEvent = (rawEvent: string) => {
    const lines = rawEvent.split(/\r?\n/)
    let eventName = "message"
    const dataLines: string[] = []
    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim()
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart())
      }
    }
    if (dataLines.length === 0) return
    const data = JSON.parse(dataLines.join("\n"))
    if (eventName === "delta") {
      handlers.onDelta?.(String(data.content ?? ""))
    } else if (eventName === "stage") {
      handlers.onStage?.(String(data.message ?? ""))
    } else if (eventName === "done") {
      finalPayload = data as T
    } else if (eventName === "error") {
      throw new Error(String(data.error || "Advisor stream failed"))
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split("\n\n")
    buffer = events.pop() ?? ""
    for (const event of events) {
      if (event.trim()) processEvent(event)
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) processEvent(buffer)
  if (!finalPayload) {
    throw new Error("Advisor stream ended before a final response arrived")
  }
  return finalPayload
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

  answerStream: (bookId: string, question: string, currentChapter: number, handlers?: AdvisorStreamHandlers) =>
    requestSse<GroundedAnswer>(intelligencePath(bookId, "/qa-stream"), {
      payload: { question, current_chapter: currentChapter },
    }, handlers),

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

  advisorMessageStream: (bookId: string, messages: AdvisorMessage[], totalChapters: number, handlers?: AdvisorStreamHandlers) =>
    requestSse<AdvisorResponse>(intelligencePath(bookId, "/advisor/message-stream"), {
      payload: {
        messages,
        total_chapters: totalChapters,
      },
    }, handlers),

  advisorSuggestions: (bookId: string) =>
    apiClient.get<AdvisorSuggestionsResponse>(intelligencePath(bookId, "/advisor/suggestions")).then(r => r.data),

  editorialReview: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<EditorialReviewResponse>(intelligencePath(bookId, "/advisor/editorial-review"), {
      text: clampAdvisorPassage(text),
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  editorialReviewStream: (bookId: string, text: string, chapterNum?: number, handlers?: AdvisorStreamHandlers) =>
    requestSse<EditorialReviewResponse>(intelligencePath(bookId, "/advisor/editorial-review-stream"), {
      payload: {
        text: clampAdvisorPassage(text),
        chapter_num: chapterNum ?? null,
      },
    }, handlers),
  proseTighten: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<ProseTightenResponse>(intelligencePath(bookId, "/advisor/prose-tighten"), {
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  proseTightenStream: (bookId: string, text: string, chapterNum?: number, handlers?: AdvisorStreamHandlers) =>
    requestSse<ProseTightenResponse>(intelligencePath(bookId, "/advisor/prose-tighten-stream"), {
      payload: {
        text,
        chapter_num: chapterNum ?? null,
      },
    }, handlers),
  whatsTheWord: (bookId: string, description: string, previousWord?: string | null) =>
    apiClient.post<WhatsTheWordResponse>(intelligencePath(bookId, "/advisor/whats-the-word"), {
      description,
      previous_word: previousWord ?? null,
    }).then(r => r.data),
  whatsTheWordStream: (bookId: string, description: string, previousWord?: string | null, handlers?: AdvisorStreamHandlers) =>
    requestSse<WhatsTheWordResponse>(intelligencePath(bookId, "/advisor/whats-the-word-stream"), {
      payload: {
        description,
        previous_word: previousWord ?? null,
      },
    }, handlers),
  inlineContinuity: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<InlineContinuityResponse>(intelligencePath(bookId, "/advisor/inline-continuity"), {
      text: clampAdvisorPassage(text),
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  inlineContinuityStream: (bookId: string, text: string, chapterNum?: number, handlers?: AdvisorStreamHandlers) =>
    requestSse<InlineContinuityResponse>(intelligencePath(bookId, "/advisor/inline-continuity-stream"), {
      payload: {
        text: clampAdvisorPassage(text),
        chapter_num: chapterNum ?? null,
      },
    }, handlers),
  voiceConsistencyReview: (bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<VoiceConsistencyResponse>(intelligencePath(bookId, "/advisor/voice-consistency"), {
      text: clampAdvisorPassage(text),
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  voiceConsistencyReviewStream: (bookId: string, text: string, chapterNum?: number, handlers?: AdvisorStreamHandlers) =>
    requestSse<VoiceConsistencyResponse>(intelligencePath(bookId, "/advisor/voice-consistency-stream"), {
      payload: {
        text: clampAdvisorPassage(text),
        chapter_num: chapterNum ?? null,
      },
    }, handlers),
  continuityReport: (bookId: string, text: string, format: ContinuityReportFormat, chapterNum?: number) =>
    apiClient.get<Blob>(intelligencePath(bookId, "/advisor/continuity-report"), {
      params: { text, format, chapter_num: chapterNum ?? null },
      responseType: "blob",
    }).then(r => r.data),
  synopsis: (bookId: string, spoilerLevel: "minimal" | "none" = "minimal") =>
    apiClient.get<ManuscriptSynopsis>(intelligencePath(bookId, "/advisor/synopsis"), {
      params: { spoiler_level: spoilerLevel },
    }).then(r => r.data),
  synopsisStream: (bookId: string, spoilerLevel: "minimal" | "none" = "minimal", handlers?: AdvisorStreamHandlers) =>
    requestSse<ManuscriptSynopsis>(`${intelligencePath(bookId, "/advisor/synopsis-stream")}?spoiler_level=${encodeURIComponent(spoilerLevel)}`, {
      method: "GET",
    }, handlers),

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

  seriesAdvisorMessageStream: (seriesId: string, messages: AdvisorMessage[], handlers?: AdvisorStreamHandlers) =>
    requestSse<AdvisorResponse>(`/intelligence/series/${seriesId}/advisor/message-stream`, {
      payload: { messages },
    }, handlers),

  seriesContinuityCheck: (seriesId: string, bookId: string, text: string, chapterNum?: number) =>
    apiClient.post<SeriesContinuityResponse>(`/intelligence/series/${seriesId}/continuity-check`, {
      book_id: normalizeBookRouteId(bookId),
      text,
      chapter_num: chapterNum ?? null,
    }).then(r => r.data),
  seriesContinuityCheckStream: (seriesId: string, bookId: string, text: string, chapterNum?: number, handlers?: AdvisorStreamHandlers) =>
    requestSse<SeriesContinuityResponse>(`/intelligence/series/${seriesId}/continuity-check-stream`, {
      payload: {
        book_id: normalizeBookRouteId(bookId),
        text,
        chapter_num: chapterNum ?? null,
      },
    }, handlers),
}
