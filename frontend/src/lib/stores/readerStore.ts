import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { SummaryMode } from "@/types/reader"

interface ReaderStore {
  summaryMode: SummaryMode
  setSummaryMode: (mode: SummaryMode) => void
  panelOpen: boolean
  setPanelOpen: (open: boolean) => void
  // Track first-tap per character per book (for context panel auto-open)
  tappedCharacters: Record<string, Set<string>>
  markTapped: (bookId: string, characterId: string) => void
  hasTapped: (bookId: string, characterId: string) => boolean
}

export const useReaderStore = create<ReaderStore>()(
  persist(
    (set, get) => ({
      summaryMode: "short",
      setSummaryMode: (summaryMode) => set({ summaryMode }),
      panelOpen: false,
      setPanelOpen: (panelOpen) => set({ panelOpen }),
      tappedCharacters: {},
      markTapped: (bookId, characterId) => {
        const current = get().tappedCharacters
        const s = new Set(current[bookId] ?? [])
        s.add(characterId)
        set({ tappedCharacters: { ...current, [bookId]: s } })
      },
      hasTapped: (bookId, characterId) => {
        const s = get().tappedCharacters[bookId]
        return s ? s.has(characterId) : false
      },
    }),
    { name: "lorevia-reader", partialize: (s) => ({ summaryMode: s.summaryMode }) }
  )
)
