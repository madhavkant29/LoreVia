import { apiClient } from "./client"
import { cachedGet, invalidateCachedGets } from "./requestCache"
import type { Book, BookEvents, BookNote, BookSeries, ChapterConsistencyReport, ChapterVersion, ObsidianPreview, ObsidianVaultNote, ObsidianVaultNoteSaveResult, PreWritingCheck, PublicBook, PublicBookDetail, PublicChapter, SavedQuote, UserStats } from "@/types/book"
import type { Character, CharacterShareResponse } from "@/types/character"

export interface ManuscriptImportResponse {
  book_id: string
  imported_chapters: number[]
  total_chapters: number
  mode: "reader" | "author"
  source_kind: string
  chapter_reports: ChapterConsistencyReport[]
}

function bookCacheKey(bookId: string, scope: string) {
  return `book:${bookId}:${scope}`
}

function invalidateBookCache(bookId: string) {
  invalidateCachedGets(`book:${bookId}:`)
  invalidateCachedGets("books:list:")
  invalidateCachedGets("books:stats")
  invalidateCachedGets("books:series")
}

export const booksApi = {
  list: (includeHidden = false) =>
    cachedGet(`books:list:${includeHidden ? "all" : "active"}`, 20 * 1000, () =>
      apiClient.get<Book[]>("/books", { params: { include_hidden: includeHidden } }).then(r => r.data)
    ),
  getStats: () => cachedGet("books:stats", 20 * 1000, () => apiClient.get<UserStats>("/books/stats").then(r => r.data)),
  listQuotes: () => cachedGet("books:quotes", 45 * 1000, () => apiClient.get<SavedQuote[]>("/books/quotes").then(r => r.data)),
  listNotes: () => cachedGet("books:notes", 30 * 1000, () => apiClient.get<BookNote[]>("/books/notes").then(r => r.data)),
  get: (id: string) => cachedGet(bookCacheKey(id, "detail"), 20 * 1000, () => apiClient.get<Book>(`/books/${id}`).then(r => r.data)),
  getBookNotes: (id: string) =>
    cachedGet(bookCacheKey(id, "notes"), 20 * 1000, () =>
      apiClient.get<BookNote[]>(`/books/${id}/notes`).then(r => r.data)
    ),
  getChapterReports: (id: string, limit = 12) =>
    cachedGet(bookCacheKey(id, `chapter-reports:${limit}`), 30 * 1000, () =>
      apiClient.get<ChapterConsistencyReport[]>(`/books/${id}/chapter-reports`, { params: { limit } }).then(r => r.data)
    ),
  getPreWritingCheck: (id: string, upcomingChapter?: number) =>
    cachedGet(bookCacheKey(id, `pre-writing:${upcomingChapter ?? "auto"}`), 30 * 1000, () =>
      apiClient.get<PreWritingCheck>(`/books/${id}/pre-writing-check`, { params: typeof upcomingChapter === "number" ? { upcoming_chapter: upcomingChapter } : undefined }).then(r => r.data)
    ),
  getChapterVersions: (id: string, chapterNumber: number, limit = 12) =>
    cachedGet(bookCacheKey(id, `chapter-versions:${chapterNumber}:${limit}`), 30 * 1000, () =>
      apiClient.get<ChapterVersion[]>(`/books/${id}/chapter-versions`, { params: { chapter_number: chapterNumber, limit } }).then(r => r.data)
    ),
  getCharacters: (id: string) =>
    cachedGet(bookCacheKey(id, "characters"), 45 * 1000, () =>
      apiClient.get<Character[]>(`/books/${id}/characters`).then(r => r.data)
    ),
  getEvents: (id: string) =>
    cachedGet(bookCacheKey(id, "events"), 20 * 1000, () =>
      apiClient.get<BookEvents>(`/books/${id}/events`).then(r => r.data)
    ),
  getReaderEvents: (id: string, chapter?: number) =>
    cachedGet(bookCacheKey(id, `reader-events:${chapter ?? "auto"}`), 20 * 1000, () =>
      apiClient.get<BookEvents>(`/books/${id}/events/reader`, { params: typeof chapter === "number" ? { chapter } : undefined }).then(r => r.data)
    ),
  updateCharacter: (
    bookId: string,
    characterId: string,
    payload: {
      name?: string
      aliases?: string[]
      role?: "mc" | "sc" | "background" | null
      description?: string | null
      arcSummary?: string | null
      personalityTags?: string[]
      motivations?: string[]
      fears?: string[]
    }
  ) => apiClient.put<Character>(`/books/${bookId}/characters/${characterId}`, {
    name: payload.name,
    aliases: payload.aliases,
    role: payload.role,
    description: payload.description,
    arc_summary: payload.arcSummary,
    personality_tags: payload.personalityTags,
    motivations: payload.motivations,
    fears: payload.fears,
  }).then(r => {
    invalidateBookCache(bookId)
    return r.data
  }),
  updateRelationship: (
    bookId: string,
    relationshipId: string,
    payload: {
      relType: string
      sentiment?: number | null
      description?: string | null
      fromChapter?: number | null
      toChapter?: number | null
    }
  ) => apiClient.put(`/books/${bookId}/relationships/${relationshipId}`, {
    rel_type: payload.relType,
    sentiment: payload.sentiment,
    description: payload.description,
    from_chapter: payload.fromChapter,
    to_chapter: payload.toChapter,
  }).then(r => {
    invalidateBookCache(bookId)
    return r.data
  }),
  shareCharacter: (bookId: string, characterId: string) =>
    apiClient.post<CharacterShareResponse>(`/books/${bookId}/characters/${characterId}/share`).then(r => r.data),
  exportCharacterCard: (bookId: string, characterId: string, format: "md" | "pdf" | "docx" = "pdf") =>
    apiClient.get<Blob>(`/books/${bookId}/characters/${characterId}/export`, { params: { format }, responseType: "blob" }).then(r => r.data),
  exportCharacterBible: (id: string, format: "md" | "pdf" | "docx" | "obsidian_folder" = "md") =>
    apiClient.get<Blob>(`/books/${id}/export/character-bible`, { params: { format }, responseType: "blob" }).then(r => r.data),
  previewCharacterBibleObsidian: (id: string) =>
    apiClient.get<ObsidianPreview>(`/books/${id}/export/character-bible/preview`).then(r => r.data),
  listCharacterBibleObsidianNotes: (id: string) =>
    apiClient.get<ObsidianVaultNote[]>(`/books/${id}/export/character-bible/notes`).then(r => r.data),
  saveCharacterBibleObsidianNote: (id: string, payload: { path: string; content: string }) =>
    apiClient.put<ObsidianVaultNoteSaveResult>(`/books/${id}/export/character-bible/notes`, payload).then(r => r.data),
  saveBookNote: (
    id: string,
    payload: { noteId?: string | null; chapterNumber?: number | null; title?: string | null; body: string }
  ) => apiClient.post<BookNote>(`/books/${id}/notes`, {
    note_id: payload.noteId,
    chapter_number: payload.chapterNumber,
    title: payload.title,
    body: payload.body,
  }).then(r => {
    invalidateBookCache(id)
    invalidateCachedGets("books:notes")
    return r.data
  }),
  deleteBookNote: (id: string, noteId: string) =>
    apiClient.delete(`/books/${id}/notes/${noteId}`).then(() => {
      invalidateBookCache(id)
      invalidateCachedGets("books:notes")
    }),
  archive: (id: string, archived = true) =>
    apiClient.put<Book>(`/books/${id}/archive`, null, { params: { archived } }).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  hide: async (id: string, hidden = true) => {
    try {
      const response = await apiClient.put<Book>(`/books/${id}/hide`, null, { params: { hidden } })
      invalidateBookCache(id)
      return response.data
    } catch (error) {
      if (!hidden) throw error
      const fallback = await apiClient.delete<Book>(`/books/${id}`)
      invalidateBookCache(id)
      return fallback.data
    }
  },
  listSeries: () =>
    cachedGet("books:series", 20 * 1000, () =>
      apiClient.get<BookSeries[]>("/books/series").then(r => r.data)
    ),
  createSeries: (payload: { name: string; description?: string | null }) =>
    apiClient.post<BookSeries>("/books/series", payload).then(r => {
      invalidateCachedGets("books:series")
      return r.data
    }),
  setSeries: (id: string, payload: { series_name?: string | null; series_order?: number | null }) =>
    apiClient.put<Book>(`/books/${id}/series`, payload).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  addBookToSeries: (seriesId: string, bookId: string, payload: { position?: number | null }) =>
    apiClient.post<BookSeries>(`/books/series/${seriesId}/books/${bookId}`, payload).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  removeBookFromSeries: (seriesId: string, bookId: string) =>
    apiClient.delete<BookSeries>(`/books/series/${seriesId}/books/${bookId}`).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  setSeriesBookStatus: (seriesId: string, bookId: string, markedComplete = true) =>
    apiClient.put<Book>(`/books/series/${seriesId}/books/${bookId}/status`, { marked_complete: markedComplete }).then(r => {
      invalidateBookCache(bookId)
      return r.data
    }),
  setMode: (id: string, mode: "reader" | "author") =>
    apiClient.put<Book>(`/books/${id}/mode`, { mode }).then(r => {
      invalidateBookCache(id)
      return r.data
    }),
  upload: (
    file: File,
    title: string,
    genre?: string,
    author?: string,
    options?: {
      visibility?: "private" | "public"
      description?: string
      seriesIds?: string[]
      autoExtractCover?: boolean
      coverFile?: File | null
      mode?: "reader" | "author"
      onProgress?: (percent: number) => void
    }
  ) => {
    const form = new FormData()
    form.append("file", file)
    form.append("title", title)
    if (genre) form.append("genre", genre)
    if (author) form.append("author", author)
    if (options?.visibility) form.append("visibility", options.visibility)
    if (options?.description) form.append("description", options.description)
    options?.seriesIds?.forEach((seriesId) => {
      if (seriesId) form.append("series_ids", seriesId)
    })
    if (options?.mode) form.append("mode", options.mode)
    form.append("auto_extract_cover", options?.autoExtractCover === false ? "false" : "true")
    if (options?.coverFile) form.append("cover_file", options.coverFile)
    return apiClient.post("/books/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (!options?.onProgress || !event.total) return
        const percent = Math.min(100, Math.max(0, Math.round((event.loaded / event.total) * 100)))
        options.onProgress(percent)
      },
    }).then(r => {
      invalidateCachedGets("books:list:")
      invalidateCachedGets("books:stats")
      return r.data
    })
  },
  importManuscript: (
    bookId: string,
    payload: {
      text?: string
      html?: string
      title?: string
      chapterNumber?: number
      replaceExisting?: boolean
      chunkLongDocuments?: boolean
      splitIntoChapters?: boolean
      files?: File[]
    }
  ) => {
    const form = new FormData()
    if (payload.text) form.append("text", payload.text)
    if (payload.html) form.append("html", payload.html)
    if (payload.title) form.append("title", payload.title)
    if (typeof payload.chapterNumber === "number") form.append("chapter_number", String(payload.chapterNumber))
    if (payload.replaceExisting) form.append("replace_existing", "true")
    if (payload.chunkLongDocuments) form.append("chunk_long_documents", "true")
    if (payload.splitIntoChapters === false) form.append("split_into_chapters", "false")
    payload.files?.forEach((file) => form.append("files", file))
    return apiClient.post<ManuscriptImportResponse>(`/books/${bookId}/manuscript/import`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then(r => {
      invalidateBookCache(bookId)
      return r.data
    })
  },
  exportManuscript: (bookId: string, format: "pdf" | "docx" = "docx") =>
    apiClient.get<Blob>(`/books/${bookId}/manuscript/export`, {
      params: { format },
      responseType: "blob",
    }).then(r => r.data),
  delete: (id: string) => apiClient.delete<Book>(`/books/${id}`).then(r => {
    invalidateBookCache(id)
    return r.data
  }),
  listPublic: () => apiClient.get<PublicBook[]>("/public/books").then(r => r.data),
  getPublic: (id: string) => apiClient.get<PublicBookDetail>(`/public/books/${id}`).then(r => r.data),
  getPublicChapter: (id: string, chapter: number) =>
    apiClient.get<PublicChapter>(`/public/books/${id}/chapter/${chapter}`).then(r => r.data),
  createPublicManual: (payload: {
    title: string
    author?: string
    genre?: string
    description?: string
    chapters: Array<{ title: string; description?: string; text: string }>
  }) => apiClient.post("/public/books/manual", payload).then(r => r.data),
  appendPublicChapter: (bookId: string, payload: { title: string; description?: string; text: string }) =>
    apiClient.post(`/public/books/${bookId}/chapters`, payload).then(r => r.data),
}
