import { apiClient } from "./client"
import type { Book, BookSeries, PublicBook, PublicBookDetail, PublicChapter, SavedQuote, UserStats } from "@/types/book"
import type { Character } from "@/types/character"

export const booksApi = {
  list: (includeHidden = false) =>
    apiClient.get<Book[]>("/books", { params: { include_hidden: includeHidden } }).then(r => r.data),
  getStats: () => apiClient.get<UserStats>("/books/stats").then(r => r.data),
  listQuotes: () => apiClient.get<SavedQuote[]>("/books/quotes").then(r => r.data),
  get: (id: string) => apiClient.get<Book>(`/books/${id}`).then(r => r.data),
  getCharacters: (id: string) => apiClient.get<Character[]>(`/books/${id}/characters`).then(r => r.data),
  archive: (id: string, archived = true) =>
    apiClient.put<Book>(`/books/${id}/archive`, null, { params: { archived } }).then(r => r.data),
  hide: async (id: string, hidden = true) => {
    try {
      const response = await apiClient.put<Book>(`/books/${id}/hide`, null, { params: { hidden } })
      return response.data
    } catch (error) {
      if (!hidden) throw error
      const fallback = await apiClient.delete<Book>(`/books/${id}`)
      return fallback.data
    }
  },
  listSeries: () =>
    apiClient.get<BookSeries[]>("/books/series").then(r => r.data),
  createSeries: (payload: { name: string; description?: string | null }) =>
    apiClient.post<BookSeries>("/books/series", payload).then(r => r.data),
  setSeries: (id: string, payload: { series_name?: string | null; series_order?: number | null }) =>
    apiClient.put<Book>(`/books/${id}/series`, payload).then(r => r.data),
  addBookToSeries: (seriesId: string, bookId: string, payload: { position?: number | null }) =>
    apiClient.post<BookSeries>(`/books/series/${seriesId}/books/${bookId}`, payload).then(r => r.data),
  removeBookFromSeries: (seriesId: string, bookId: string) =>
    apiClient.delete<BookSeries>(`/books/series/${seriesId}/books/${bookId}`).then(r => r.data),
  setSeriesBookStatus: (seriesId: string, bookId: string, markedComplete = true) =>
    apiClient.put<Book>(`/books/series/${seriesId}/books/${bookId}/status`, { marked_complete: markedComplete }).then(r => r.data),
  upload: (
    file: File,
    title: string,
    genre?: string,
    author?: string,
    options?: {
      visibility?: "private" | "public"
      description?: string
      autoExtractCover?: boolean
      coverFile?: File | null
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
    form.append("auto_extract_cover", options?.autoExtractCover === false ? "false" : "true")
    if (options?.coverFile) form.append("cover_file", options.coverFile)
    return apiClient.post("/books/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (!options?.onProgress || !event.total) return
        const percent = Math.min(100, Math.max(0, Math.round((event.loaded / event.total) * 100)))
        options.onProgress(percent)
      },
    }).then(r => r.data)
  },
  delete: (id: string) => apiClient.delete<Book>(`/books/${id}`).then(r => r.data),
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
