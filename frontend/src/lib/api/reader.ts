import { apiClient } from "./client"
import type { ChapterData, ChapterListResponse, ContextResult, ChapterSummary, ForeshadowingItem, PlotThread, ReadingProgress, RelationshipEvolutionPair, SummaryCollectionResponse, SummaryMode, ThematicSearchResult, TimelineEvent } from "@/types/reader"
import type { RelationshipGraph } from "@/types/character"

export const readerApi = {
  getChapter: (bookId: string, chapter: number) =>
    apiClient.get<ChapterData>(`/reader/${bookId}/chapter/${chapter}`).then(r => r.data),
  getContext: (bookId: string, q: string, chapter: number) =>
    apiClient.get<ContextResult>(`/reader/${bookId}/context`, { params: { q, chapter } }).then(r => r.data),
  getSummary: (bookId: string, chapter: number, mode: SummaryMode) =>
    apiClient.get<ChapterSummary>(`/reader/${bookId}/summary/${chapter}`, { params: { mode } }).then(r => r.data),
  getRelationships: (bookId: string, chapter: number) =>
    apiClient.get<RelationshipGraph>(`/reader/${bookId}/relationships`, { params: { chapter } }).then(r => r.data),
  search: (bookId: string, q: string, chapter: number) =>
    apiClient.get(`/reader/${bookId}/search`, { params: { q, chapter } }).then(r => r.data),
  getChapterList: (bookId: string) =>
    apiClient.get<ChapterListResponse>(`/reader/${bookId}/chapters`).then(r => r.data),
  getSummaryCollection: (bookId: string) =>
    apiClient.get<SummaryCollectionResponse>(`/reader/${bookId}/summary-collection`).then(r => r.data),
  getForeshadowing: (bookId: string) =>
    apiClient.get<{ items: ForeshadowingItem[] }>(`/reader/${bookId}/foreshadowing`).then(r => r.data),
  getTimeline: (bookId: string) =>
    apiClient.get<{ events: TimelineEvent[] }>(`/reader/${bookId}/timeline`).then(r => r.data),
  thematicSearch: (bookId: string, q: string) =>
    apiClient.get<{ results: ThematicSearchResult[] }>(`/reader/${bookId}/thematic-search`, { params: { q } }).then(r => r.data),
  getRelationshipEvolution: (bookId: string, chapter: number) =>
    apiClient.get<{ pairs: RelationshipEvolutionPair[] }>(`/reader/${bookId}/relationship-evolution`, { params: { chapter } }).then(r => r.data),
  getPlotThreads: (bookId: string, chapter: number) =>
    apiClient.get<PlotThread[]>(`/reader/${bookId}/plot-threads`, { params: { chapter } }).then(r => r.data),
  getRecall: (bookId: string) =>
    apiClient.get(`/reader/${bookId}/recall`).then(r => r.data),
  getProgress: (bookId: string) =>
    apiClient.get<ReadingProgress>(`/reader/${bookId}/progress`).then(r => r.data),
  updateProgress: (bookId: string, chapter: number, scrollPct: number) =>
    apiClient.put(`/reader/${bookId}/progress`, null, { params: { current_chapter: chapter, scroll_pct: scrollPct } }),
  updateChapterReadStatus: (bookId: string, chapter: number, read: boolean) =>
    apiClient.put(`/reader/${bookId}/progress/chapter-status`, null, { params: { chapter, read } }).then(r => r.data),
  markBookRead: (bookId: string) =>
    apiClient.put(`/reader/${bookId}/progress/mark-book-read`).then(r => r.data),
  saveQuote: (bookId: string, payload: { quote_text: string; chapter_number?: number; character_name?: string | null; note?: string | null }) =>
    apiClient.post(`/reader/${bookId}/quotes`, payload).then(r => r.data),
}
