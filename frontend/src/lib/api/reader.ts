import { apiClient } from "./client"
import { cachedGet, invalidateCachedGets } from "./requestCache"
import type { ChapterData, ChapterListResponse, ContextResult, ChapterSummary, ForeshadowingItem, PlotThread, ReadingProgress, RelationshipEvolutionPair, SummaryCollectionResponse, SummaryMode, ThematicSearchResult, TimelineResponse } from "@/types/reader"
import type { RelationshipGraph } from "@/types/character"

function readerCacheKey(bookId: string, scope: string) {
  return `reader:${bookId}:${scope}`
}

export const readerApi = {
  getChapter: (bookId: string, chapter: number) =>
    cachedGet(readerCacheKey(bookId, `chapter:${chapter}`), 5 * 60 * 1000, () =>
      apiClient.get<ChapterData>(`/reader/${bookId}/chapter/${chapter}`).then(r => r.data)
    ),
  getContext: (bookId: string, q: string, chapter: number) =>
    cachedGet(readerCacheKey(bookId, `context:${chapter}:${q}`), 30 * 1000, () =>
      apiClient.get<ContextResult>(`/reader/${bookId}/context`, { params: { q, chapter } }).then(r => r.data)
    ),
  getSummary: (bookId: string, chapter: number, mode: SummaryMode) =>
    cachedGet(readerCacheKey(bookId, `summary:${chapter}:${mode}`), 2 * 60 * 1000, () =>
      apiClient.get<ChapterSummary>(`/reader/${bookId}/summary/${chapter}`, { params: { mode } }).then(r => r.data)
    ),
  getRelationships: (bookId: string, chapter: number) =>
    cachedGet(readerCacheKey(bookId, `relationships:${chapter}`), 45 * 1000, () =>
      apiClient.get<RelationshipGraph>(`/reader/${bookId}/relationships`, { params: { chapter } }).then(r => r.data)
    ),
  search: (bookId: string, q: string, chapter: number) =>
    cachedGet(readerCacheKey(bookId, `search:${chapter}:${q}`), 30 * 1000, () =>
      apiClient.get(`/reader/${bookId}/search`, { params: { q, chapter } }).then(r => r.data)
    ),
  getChapterList: (bookId: string) =>
    cachedGet(readerCacheKey(bookId, "chapters"), 30 * 1000, () =>
      apiClient.get<ChapterListResponse>(`/reader/${bookId}/chapters`).then(r => r.data)
    ),
  getSummaryCollection: (bookId: string) =>
    cachedGet(readerCacheKey(bookId, "summary-collection"), 45 * 1000, () =>
      apiClient.get<SummaryCollectionResponse>(`/reader/${bookId}/summary-collection`).then(r => r.data)
    ),
  getForeshadowing: (bookId: string) =>
    cachedGet(readerCacheKey(bookId, "foreshadowing"), 45 * 1000, () =>
      apiClient.get<{ items: ForeshadowingItem[] }>(`/reader/${bookId}/foreshadowing`).then(r => r.data)
    ),
  getTimeline: (bookId: string) =>
    cachedGet(readerCacheKey(bookId, "timeline"), 45 * 1000, () =>
      apiClient.get<TimelineResponse>(`/reader/${bookId}/timeline`).then(r => r.data)
    ),
  thematicSearch: (bookId: string, q: string) =>
    cachedGet(readerCacheKey(bookId, `thematic-search:${q}`), 30 * 1000, () =>
      apiClient.get<{ results: ThematicSearchResult[] }>(`/reader/${bookId}/thematic-search`, { params: { q } }).then(r => r.data)
    ),
  getRelationshipEvolution: (bookId: string, chapter: number) =>
    cachedGet(readerCacheKey(bookId, `relationship-evolution:${chapter}`), 45 * 1000, () =>
      apiClient.get<{ pairs: RelationshipEvolutionPair[] }>(`/reader/${bookId}/relationship-evolution`, { params: { chapter } }).then(r => r.data)
    ),
  getPlotThreads: (bookId: string, chapter?: number) =>
    cachedGet(readerCacheKey(bookId, `plot-threads:${chapter ?? "all"}`), 45 * 1000, () =>
      apiClient.get<PlotThread[]>(`/reader/${bookId}/plot-threads`, { params: chapter ? { chapter } : undefined }).then(r => r.data)
    ),
  updatePlotThread: (bookId: string, threadId: string, payload: { note: string | null }) =>
    apiClient.put<PlotThread>(`/reader/${bookId}/plot-threads/${threadId}`, payload).then(r => {
      invalidateCachedGets(readerCacheKey(bookId, "plot-threads:"))
      invalidateCachedGets(readerCacheKey(bookId, "timeline"))
      return r.data
    }),
  getRecall: (bookId: string) =>
    cachedGet(readerCacheKey(bookId, "recall"), 30 * 1000, () =>
      apiClient.get(`/reader/${bookId}/recall`).then(r => r.data)
    ),
  getProgress: (bookId: string) =>
    cachedGet(readerCacheKey(bookId, "progress"), 12 * 1000, () =>
      apiClient.get<ReadingProgress>(`/reader/${bookId}/progress`).then(r => r.data)
    ),
  updateProgress: (bookId: string, chapter: number, scrollPct: number) =>
    apiClient.put(`/reader/${bookId}/progress`, null, { params: { current_chapter: chapter, scroll_pct: scrollPct } }).then((response) => {
      invalidateCachedGets(readerCacheKey(bookId, "progress"))
      return response
    }),
  updateChapterReadStatus: (bookId: string, chapter: number, read: boolean) =>
    apiClient.put(`/reader/${bookId}/progress/chapter-status`, null, { params: { chapter, read } }).then(r => {
      invalidateCachedGets(readerCacheKey(bookId, "progress"))
      invalidateCachedGets(readerCacheKey(bookId, "chapters"))
      invalidateCachedGets(readerCacheKey(bookId, "summary-collection"))
      invalidateCachedGets(readerCacheKey(bookId, `summary:${chapter}:`))
      return r.data
    }),
  markBookRead: (bookId: string) =>
    apiClient.put(`/reader/${bookId}/progress/mark-book-read`).then(r => {
      invalidateCachedGets(readerCacheKey(bookId, "progress"))
      invalidateCachedGets(readerCacheKey(bookId, "chapters"))
      invalidateCachedGets(readerCacheKey(bookId, "summary-collection"))
      return r.data
    }),
  saveQuote: (bookId: string, payload: { quote_text: string; chapter_number?: number; character_name?: string | null; note?: string | null }) =>
    apiClient.post(`/reader/${bookId}/quotes`, payload).then(r => {
      invalidateCachedGets("books:quotes")
      return r.data
    }),
}
