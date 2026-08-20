"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export type BookMode = "reader" | "author"

interface BookModeStore {
  modesByBookId: Record<string, BookMode>
  getMode: (bookId: string) => BookMode
  setMode: (bookId: string, mode: BookMode) => void
  clearMode: (bookId: string) => void
  clearAllModes: () => void
}

export const useBookModeStore = create<BookModeStore>()(
  persist(
    (set, get) => ({
      modesByBookId: {},
      getMode: (bookId) => get().modesByBookId[bookId] ?? "reader",
      setMode: (bookId, mode) =>
        set((state) => ({
          modesByBookId: { ...state.modesByBookId, [bookId]: mode },
        })),
      clearMode: (bookId) =>
        set((state) => {
          const next = { ...state.modesByBookId }
          delete next[bookId]
          return { modesByBookId: next }
        }),
      clearAllModes: () => set({ modesByBookId: {} }),
    }),
    { name: "lorevia-book-modes" }
  )
)
