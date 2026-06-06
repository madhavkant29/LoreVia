import { apiClient } from "./client"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type {
  CanonOverride,
  WorldBuildingDocument,
  WorldBuildingDocumentDetail,
  WorldGapResult,
  WorldIntegrationResult,
  WorldNote,
  WorldElement,
  WorldQueryResponse,
  WikiEntry,
  WikiGenerationResponse,
} from "@/types/world-building"

function worldBuildingPath(bookId: string, suffix = "") {
  return `/intelligence/${normalizeBookRouteId(bookId)}${suffix}`
}

export const worldBuildingApi = {
  listDocuments: (bookId: string, includeInactive = false) =>
    apiClient.get<WorldBuildingDocument[]>(worldBuildingPath(bookId, "/world-building/documents"), {
      params: includeInactive ? { include_inactive: true } : undefined,
    }).then(r => r.data),
  uploadDocuments: (
    bookId: string,
    payload: {
      title?: string
      text?: string
      html?: string
      replaceExisting?: boolean
      files?: File[]
    }
  ) => {
    const form = new FormData()
    if (payload.title) form.append("title", payload.title)
    if (payload.text) form.append("text", payload.text)
    if (payload.html) form.append("html", payload.html)
    if (payload.replaceExisting) form.append("replace_existing", "true")
    payload.files?.forEach((file) => form.append("files", file))
    return apiClient.post<WorldBuildingDocument[]>(worldBuildingPath(bookId, "/world-building/documents"), form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then(r => r.data)
  },
  getDocument: (bookId: string, documentId: string) =>
    apiClient.get<WorldBuildingDocumentDetail>(worldBuildingPath(bookId, `/world-building/documents/${documentId}`)).then(r => r.data),
  updateDocument: (
    bookId: string,
    documentId: string,
    payload: { title?: string | null; text: string; html?: string | null }
  ) =>
    apiClient.patch<WorldBuildingDocumentDetail>(worldBuildingPath(bookId, `/world-building/documents/${documentId}`), payload).then(r => r.data),
  deleteDocument: (bookId: string, documentId: string) =>
    apiClient.delete(worldBuildingPath(bookId, `/world-building/documents/${documentId}`)).then(() => undefined),
  analyze: (bookId: string, payload: { mode?: string | null; query?: string | null; auto_create_notes?: boolean }) =>
    apiClient.post<WorldGapResult | WorldIntegrationResult>(worldBuildingPath(bookId, "/world-building/analyze"), payload).then(r => r.data),
  getGaps: (bookId: string) =>
    apiClient.get<WorldGapResult>(worldBuildingPath(bookId, "/world-building/gaps")).then(r => r.data),
  getIntegration: (bookId: string) =>
    apiClient.get<WorldIntegrationResult>(worldBuildingPath(bookId, "/world-building/integration")).then(r => r.data),
  listElements: (bookId: string) =>
    apiClient.get<WorldElement[]>(worldBuildingPath(bookId, "/world-building/elements")).then(r => r.data),
  query: (bookId: string, payload: { query: string; mode?: string | null }) =>
    apiClient.post<WorldQueryResponse>(worldBuildingPath(bookId, "/world-building/query"), payload).then(r => r.data),
  listWiki: (bookId: string) =>
    apiClient.get<WikiEntry[]>(worldBuildingPath(bookId, "/world-building/wiki")).then(r => r.data),
  generateWiki: (bookId: string) =>
    apiClient.post<WikiGenerationResponse>(worldBuildingPath(bookId, "/world-building/wiki/generate")).then(r => r.data),
  getSeriesAnalysis: (seriesId: string) =>
    apiClient.get(`/intelligence/series/${seriesId}/world-building/series-analysis`).then(r => r.data),
  acceptSuggestion: (worldElementId: string, payload: { suggestion_id: string; mark_implemented?: boolean }) =>
    apiClient.post<{ accepted: string; remaining: number }>(`/intelligence/${worldElementId}/world-building/accept-suggestion`, payload).then(r => r.data),
  listNotes: (bookId: string) =>
    apiClient.get<WorldNote[]>(worldBuildingPath(bookId, "/world-building/notes")).then(r => r.data),
  getNotesByChapter: (bookId: string, chapterNumber: number) =>
    apiClient.get<WorldNote[]>(worldBuildingPath(bookId, `/world-building/notes/by-chapter/${chapterNumber}`)).then(r => r.data),
  createNote: (
    bookId: string,
    payload: {
      world_element_id?: string | null
      world_document_id?: string | null
      note_type?: string
      chapter_number?: number | null
      title?: string | null
      body: string
      priority?: string
      status?: string
      linked_gap_id?: string | null
      linked_integration_id?: string | null
      context_label?: string | null
      suggested_fix?: string | null
    }
  ) => apiClient.post<WorldNote>(worldBuildingPath(bookId, "/world-building/notes"), payload).then(r => r.data),
  updateNoteStatus: (bookId: string, noteId: string, status: string) =>
    apiClient.patch<WorldNote>(worldBuildingPath(bookId, `/world-building/notes/${noteId}/status`), { status }).then(r => r.data),
  deleteNote: (bookId: string, noteId: string) =>
    apiClient.delete(worldBuildingPath(bookId, `/world-building/notes/${noteId}`)).then(r => r.data),
  listCanonOverrides: (bookId: string) =>
    apiClient.get<CanonOverride[]>(worldBuildingPath(bookId, "/world-building/canon-overrides")).then(r => r.data),
  saveCanonOverride: (
    bookId: string,
    payload: { canonical_name: string; aliases?: string[]; entity_type?: string | null; notes?: string | null }
  ) => apiClient.post<CanonOverride>(worldBuildingPath(bookId, "/world-building/canon-overrides"), payload).then(r => r.data),
}
