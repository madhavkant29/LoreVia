import { apiClient } from "./client"
import { readerCacheKey } from "@/lib/query/cacheKeys"
import { invalidateQueryKeys } from "@/lib/query/queryClient"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type { BetaReadAssignment, BetaReadAssignmentListResponse, ChapterData, ChapterListResponse, ContextResult, ChapterSummary, ForeshadowingItem, PlotThread, ReadingProgress, RecallResponse, RelationshipEvolutionPair, SummaryCollectionResponse, SummaryMode, ThematicSearchResult, TimelineResponse } from "@/types/reader"
import type { RelationshipGraph } from "@/types/character"

function readerPath(bookId: string, suffix = "") {
  return `/reader/${normalizeBookRouteId(bookId)}${suffix}`
}

function invalidateBetaReadCache() {
  void invalidateQueryKeys("reader:beta-reads:")
  void invalidateQueryKeys("books:list:")
}

export const readerApi = {
  getChapter: (bookId: string, chapter: number) =>
    apiClient.get<ChapterData>(readerPath(bookId, `/chapter/${chapter}`), {
      params: { include: "characters,media,tags,beta_feedback,text_content,html_content,text_url" },
    }).then(r => r.data),
  getContext: (bookId: string, q: string, chapter: number) =>
    apiClient.get<ContextResult>(readerPath(bookId, "/context"), { params: { q, chapter } }).then(r => r.data),
  getSummary: (bookId: string, chapter: number, mode: SummaryMode) =>
    apiClient.get<ChapterSummary>(readerPath(bookId, `/summary/${chapter}`), { params: { mode } }).then(r => r.data),
  getRelationships: (bookId: string, chapter: number, options?: { includeInactive?: boolean; limit?: number; offset?: number; include?: string }) =>
    apiClient.get<RelationshipGraph>(readerPath(bookId, "/relationships"), {
      params: { chapter, include_inactive: options?.includeInactive ?? false, limit: options?.limit ?? 100, offset: options?.offset ?? 0, include: options?.include },
    }).then(r => r.data),
  search: (bookId: string, q: string, chapter: number) =>
    apiClient.get(readerPath(bookId, "/search"), { params: { q, chapter } }).then(r => r.data),
  getChapterList: (bookId: string) =>
    apiClient.get<ChapterListResponse>(readerPath(bookId, "/chapters")).then(r => r.data),
  getSummaryCollection: (bookId: string) =>
    apiClient.get<SummaryCollectionResponse>(readerPath(bookId, "/summary-collection")).then(r => r.data),
  getForeshadowing: (bookId: string) =>
    apiClient.get<{ items: ForeshadowingItem[] }>(readerPath(bookId, "/foreshadowing")).then(r => r.data),
  getTimeline: (bookId: string, options?: { limit?: number; offset?: number }) =>
    apiClient.get<TimelineResponse>(readerPath(bookId, "/timeline"), { params: { limit: options?.limit ?? 100, offset: options?.offset ?? 0, include: "chapters,character_tracks,thread_tracks,relationship_markers" } }).then(r => r.data),
  thematicSearch: (bookId: string, q: string) =>
    apiClient.get<{ results: ThematicSearchResult[] }>(readerPath(bookId, "/thematic-search"), { params: { q } }).then(r => r.data),
  getRelationshipEvolution: (bookId: string, chapter: number) =>
    apiClient.get<{ pairs: RelationshipEvolutionPair[] }>(readerPath(bookId, "/relationship-evolution"), { params: { chapter } }).then(r => r.data),
  getPlotThreads: (bookId: string, chapter?: number) =>
    apiClient.get<PlotThread[]>(readerPath(bookId, "/plot-threads"), { params: chapter ? { chapter } : undefined }).then(r => r.data),
  updatePlotThread: (bookId: string, threadId: string, payload: { note: string | null; status?: string | null }) =>
    apiClient.put<PlotThread>(readerPath(bookId, `/plot-threads/${threadId}`), payload).then(r => {
      void invalidateQueryKeys(readerCacheKey(bookId, "plot-threads:"))
      void invalidateQueryKeys(readerCacheKey(bookId, "timeline"))
      return r.data
    }),
  getRecall: (bookId: string) =>
    apiClient.get<RecallResponse>(readerPath(bookId, "/recall")).then(r => r.data),
  getProgress: (bookId: string) =>
    apiClient.get<ReadingProgress>(readerPath(bookId, "/progress")).then(r => r.data),
  updateProgress: (bookId: string, chapter: number, scrollPct: number) =>
    apiClient.put(readerPath(bookId, "/progress"), null, { params: { current_chapter: chapter, scroll_pct: scrollPct } }).then((response) => {
      void invalidateQueryKeys(readerCacheKey(bookId, "progress"))
      return response
    }),
  updateChapterReadStatus: (bookId: string, chapter: number, read: boolean) =>
    apiClient.put(readerPath(bookId, "/progress/chapter-status"), null, { params: { chapter, read } }).then(r => {
      void invalidateQueryKeys(readerCacheKey(bookId, "progress"))
      void invalidateQueryKeys(readerCacheKey(bookId, "chapters"))
      void invalidateQueryKeys(readerCacheKey(bookId, "summary-collection"))
      void invalidateQueryKeys(readerCacheKey(bookId, `summary:${chapter}:`))
      return r.data
    }),
  markBookRead: (bookId: string) =>
    apiClient.put(readerPath(bookId, "/progress/mark-book-read")).then(r => {
      void invalidateQueryKeys(readerCacheKey(bookId, "progress"))
      void invalidateQueryKeys(readerCacheKey(bookId, "chapters"))
      void invalidateQueryKeys(readerCacheKey(bookId, "summary-collection"))
      return r.data
    }),
  saveQuote: (bookId: string, payload: { quote_text: string; chapter_number?: number; character_name?: string | null; note?: string | null }) =>
    apiClient.post(readerPath(bookId, "/quotes"), payload).then(r => {
      void invalidateQueryKeys("books:quotes")
      return r.data
    }),
  getUpcomingBetaReads: () =>
    apiClient.get<BetaReadAssignmentListResponse>("/beta-reads/upcoming").then(r => r.data.items),
  listBetaReads: (bucket?: string) =>
    apiClient.get<BetaReadAssignmentListResponse>("/beta-reads", { params: bucket ? { bucket } : undefined }).then(r => r.data.items),
  startBetaRead: (assignmentId: string) =>
    apiClient.post<BetaReadAssignment>(`/beta-reads/${assignmentId}/start`).then(r => {
      invalidateBetaReadCache()
      return r.data
    }),
  syncBetaRead: (assignmentId: string) =>
    apiClient.post<{ assignment: BetaReadAssignment }>(`/beta-reads/${assignmentId}/sync`).then(r => {
      invalidateBetaReadCache()
      return r.data.assignment
    }),
  submitBetaReadFeedback: (assignmentId: string, finalFeedback: string, finalRating: number) =>
    apiClient.post<BetaReadAssignment>(`/beta-reads/${assignmentId}/submit-feedback`, {
      final_feedback: finalFeedback,
      final_rating: finalRating,
    }).then(r => {
      invalidateBetaReadCache()
      return r.data
    }),
}
