import { apiClient } from "./client"
import type { Book } from "@/types/book"
import type { Character } from "@/types/character"

export const booksApi = {
  list: () => apiClient.get<Book[]>("/books").then(r => r.data),
  get: (id: string) => apiClient.get<Book>(`/books/${id}`).then(r => r.data),
  getCharacters: (id: string) => apiClient.get<Character[]>(`/books/${id}/characters`).then(r => r.data),
  upload: (file: File, title: string, genre?: string, author?: string) => {
    const form = new FormData()
    form.append("file", file)
    form.append("title", title)
    if (genre) form.append("genre", genre)
    if (author) form.append("author", author)
    return apiClient.post("/books/upload", form, { headers: { "Content-Type": "multipart/form-data" } }).then(r => r.data)
  },
  delete: (id: string) => apiClient.delete(`/books/${id}`),
}
