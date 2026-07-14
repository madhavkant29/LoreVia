import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { capture, captureTiming } from "@/lib/analytics/posthog"
import type { SaveState, WriterWorkspace } from "@/types/book"
import type { SaveTarget } from "./manuscriptPage.constants"

type SetTargetSaveState = (target: SaveTarget, state: SaveState) => void
type SetTargetRetry = (target: SaveTarget, retry: (() => Promise<void>) | null) => void

type UseManuscriptWorkspacePersistenceArgs = {
  bookId: string
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  setTargetRetry: SetTargetRetry
  setTargetSaveState: SetTargetSaveState
  setWorkspaceSaving: Dispatch<SetStateAction<boolean>>
  setWriterWorkspace: Dispatch<SetStateAction<WriterWorkspace | null>>
}

export function useManuscriptWorkspacePersistence({
  bookId,
  setStatusMessage,
  setTargetRetry,
  setTargetSaveState,
  setWorkspaceSaving,
  setWriterWorkspace,
}: UseManuscriptWorkspacePersistenceArgs) {
  async function saveWorkspace(patch: Partial<WriterWorkspace>, options?: { silent?: boolean }) {
    const startedAt = typeof performance !== "undefined" ? performance.now() : 0
    const target: SaveTarget = patch.corkboard_cards ? "corkboard" : "workspace"
    setTargetSaveState(target, "saving")
    setTargetRetry(target, null)
    setWriterWorkspace((current) => current ? { ...current, ...patch } : current)
    setWorkspaceSaving(true)
    try {
      const updated = await booksApi.updateWriterWorkspace(bookId, patch)
      setWriterWorkspace(updated)
      setTargetSaveState(target, "saved")
      captureTiming("save_latency_ms", startedAt, { book_id: bookId, save_target: target })
      if (!options?.silent) setStatusMessage("Workspace preferences saved.")
    } catch {
      setTargetSaveState(target, "error")
      setTargetRetry(target, () => saveWorkspace(patch, options))
      captureTiming("save_latency_ms", startedAt, { book_id: bookId, save_target: target, save_state: "error" })
      capture("save_failure_count", { book_id: bookId, save_target: target })
      if (!options?.silent) setStatusMessage("Workspace save failed. Your local changes are still visible.")
    } finally {
      setWorkspaceSaving(false)
    }
  }

  return { saveWorkspace }
}
