import { useState, type Dispatch, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import type { Character } from "@/types/character"

type UseCharacterRepairActionsArgs = {
  bookId: string
  refetchCharacterReview: () => Promise<unknown>
  refetchIdentityDiagnostics: () => Promise<unknown>
  refetchRepairPreview: () => Promise<unknown>
  refreshCharacters: () => Promise<Character[]>
  refreshGraph: () => Promise<void>
  reprocessAllowDemote: boolean
  reprocessAllowMerge: boolean
  scheduleTimeout: (callback: () => void, delay: number) => void
  setActionError: Dispatch<SetStateAction<string | null>>
  setNoteToast: Dispatch<SetStateAction<string | null>>
}

export function useCharacterRepairActions({
  bookId,
  refetchCharacterReview,
  refetchIdentityDiagnostics,
  refetchRepairPreview,
  refreshCharacters,
  refreshGraph,
  reprocessAllowDemote,
  reprocessAllowMerge,
  scheduleTimeout,
  setActionError,
  setNoteToast,
}: UseCharacterRepairActionsArgs) {
  const [identityUndoActionId, setIdentityUndoActionId] = useState<string | null>(null)
  const [reprocessBusy, setReprocessBusy] = useState(false)

  async function handleApplyCharacterReprocess() {
    setReprocessBusy(true)
    setActionError(null)
    try {
      await booksApi.applyCharacterReprocess(bookId, {
        allowMergeSafePairs: reprocessAllowMerge,
        allowDemoteObviousNoise: reprocessAllowDemote,
      })
      await refreshCharacters()
      await refreshGraph()
      await refetchRepairPreview()
      await refetchIdentityDiagnostics()
      setNoteToast("Character repair applied.")
      scheduleTimeout(() => setNoteToast(null), 2200)
    } catch {
      setActionError("Could not apply the repair plan.")
    } finally {
      setReprocessBusy(false)
    }
  }

  async function handleRepairRelationships() {
    setReprocessBusy(true)
    setActionError(null)
    try {
      const result = await booksApi.repairRelationships(bookId)
      await refreshGraph()
      setNoteToast(
        `Relationship repair: ${result.pairs_repaired} pairs repaired, ${result.relationships_deleted} deleted, ${result.relationships_remaining} remaining, ${result.relationship_candidates_updated} candidates updated.`,
      )
      scheduleTimeout(() => setNoteToast(null), 4000)
    } catch {
      setActionError("Could not repair relationship timelines.")
    } finally {
      setReprocessBusy(false)
    }
  }

  async function handleUndoIdentityAction(actionId: string) {
    setIdentityUndoActionId(actionId)
    setActionError(null)
    try {
      await booksApi.undoCharacterIdentityAction(bookId, actionId)
      await refreshCharacters()
      await refetchCharacterReview()
      await refetchRepairPreview()
      await refetchIdentityDiagnostics()
      setNoteToast("Identity action undone.")
      scheduleTimeout(() => setNoteToast(null), 2200)
    } catch {
      setActionError("Could not undo this identity action.")
    } finally {
      setIdentityUndoActionId(null)
    }
  }

  return {
    handleApplyCharacterReprocess,
    handleRepairRelationships,
    handleUndoIdentityAction,
    identityUndoActionId,
    reprocessBusy,
  }
}
