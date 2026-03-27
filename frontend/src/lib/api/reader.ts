import { apiClient } from "./client"
import type { ChapterData, ContextResult, ChapterSummary, RelationshipGraph, PlotThread, SummaryMode } from "@/types/reader"

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
  getPlotThreads: (bookId: string, chapter: number) =>
    apiClient.get<PlotThread[]>(`/reader/${bookId}/plot-threads`, { params: { chapter } }).then(r => r.data),
  getRecall: (bookId: string) =>
    apiClient.get(`/reader/${bookId}/recall`).then(r => r.data),
  getProgress: (bookId: string) =>
    apiClient.get(`/reader/${bookId}/progress`).then(r => r.data),
  updateProgress: (bookId: string, chapter: number, scrollPct: number) =>
    apiClient.put(`/reader/${bookId}/progress`, null, { params: { current_chapter: chapter, scroll_pct: scrollPct } }),
}
