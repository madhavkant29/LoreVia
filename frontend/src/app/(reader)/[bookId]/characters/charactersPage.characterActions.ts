import { useState, type Dispatch, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import type { Character } from "@/types/character"
import type { PromptDialogConfig, ConfirmDialogConfig } from "@/types/ux"
import {
  buildRelationshipDraft,
  hasImplicitRepairProtection,
  parsePartitionTargets,
  type CreateDraft,
  type EditDraft,
  type RelationshipComposerDraft,
} from "./charactersPage.helpers"
import {
  buildCharacterCreatePayload,
  buildCharacterUpdatePayload,
  buildPartitionTargetSuggestion,
  buildRelationshipCreatePayload,
} from "./charactersPage.mutationPayloads"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type UseCharacterMutationActionsArgs = {
  bookId: string
  chars: Character[]
  confirm: (config: ConfirmDialogConfig) => Promise<boolean>
  createDraft: CreateDraft
  draft: EditDraft
  progressChapter: number
  prompt: (config: PromptDialogConfig) => Promise<string | null>
  refetchCharacterReview: () => Promise<unknown>
  refetchRepairPreview: () => Promise<unknown>
  refreshCharacters: () => Promise<Character[]>
  refreshGraph: () => Promise<void>
  relationshipChapter: number
  relationshipDraft: RelationshipComposerDraft
  reviewNoteDraft: string
  scheduleTimeout: (callback: () => void, delay: number) => void
  selectedCharacter: Character | null
  workspaceMode: WorkspaceMode
  setActionError: Dispatch<SetStateAction<string | null>>
  setActiveTab: Dispatch<SetStateAction<CharacterProfileTab>>
  setCastFilter: Dispatch<SetStateAction<"all" | "main" | "minor" | "needs-review" | "duplicates">>
  setCharacterMenuOpen: Dispatch<SetStateAction<boolean>>
  setChars: Dispatch<SetStateAction<Character[]>>
  setCreating: Dispatch<SetStateAction<boolean>>
  setEditing: Dispatch<SetStateAction<boolean>>
  setNoteToast: Dispatch<SetStateAction<string | null>>
  setRelationshipDraft: Dispatch<SetStateAction<RelationshipComposerDraft>>
  setSearch: Dispatch<SetStateAction<string>>
  setSelectedId: Dispatch<SetStateAction<string>>
  setWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>
}

export function useCharacterMutationActions({
  bookId,
  chars,
  confirm,
  createDraft,
  draft,
  progressChapter,
  prompt,
  refetchCharacterReview,
  refetchRepairPreview,
  refreshCharacters,
  refreshGraph,
  relationshipChapter,
  relationshipDraft,
  reviewNoteDraft,
  scheduleTimeout,
  selectedCharacter,
  workspaceMode,
  setActionError,
  setActiveTab,
  setCastFilter,
  setCharacterMenuOpen,
  setChars,
  setCreating,
  setEditing,
  setNoteToast,
  setRelationshipDraft,
  setSearch,
  setSelectedId,
  setWorkspaceMode,
}: UseCharacterMutationActionsArgs) {
  const [createBusy, setCreateBusy] = useState(false)
  const [createRelationshipBusy, setCreateRelationshipBusy] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [graphOverrideBusy, setGraphOverrideBusy] = useState(false)
  const [partitioning, setPartitioning] = useState(false)
  const [reviewNoteBusy, setReviewNoteBusy] = useState(false)
  const [saving, setSaving] = useState(false)

  async function handleSaveCharacter() {
    if (!selectedCharacter) return
    setSaving(true)
    setActionError(null)
    try {
      const updated = await booksApi.updateCharacter(bookId, selectedCharacter.id, {
        ...buildCharacterUpdatePayload(draft),
      })
      setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
      setSelectedId(updated.id)
      await refetchCharacterReview()
      await refreshGraph()
      setEditing(false)
    } catch {
      setActionError("Could not save character changes.")
    } finally {
      setSaving(false)
    }
  }

  async function handleGraphVisibilityOverride(override: "include" | "exclude" | null) {
    if (!selectedCharacter) return
    setGraphOverrideBusy(true)
    setActionError(null)
    try {
      const updated = await booksApi.updateCharacter(bookId, selectedCharacter.id, {
        graphVisibility: override,
      })
      setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
      await refetchCharacterReview()
      await refreshGraph()
    } catch {
      setActionError("Could not update graph visibility for this character.")
    } finally {
      setGraphOverrideBusy(false)
    }
  }

  async function handleCreateCharacter() {
    setCreateBusy(true)
    setActionError(null)
    try {
      const created = await booksApi.createCharacter(bookId, {
        ...buildCharacterCreatePayload(createDraft, progressChapter),
      })
      setChars((current) => [...current, created])
      setSelectedId(created.id)
      await refetchCharacterReview()
      await refreshGraph()
      setCreating(false)
      setCastFilter("all")
      setSearch("")
    } catch {
      setActionError("Could not create this character.")
    } finally {
      setCreateBusy(false)
    }
  }

  async function handleCreateRelationship() {
    if (!selectedCharacter || !relationshipDraft.counterpartId) {
      setActionError("Choose a counterpart before creating a relationship.")
      return
    }
    setCreateRelationshipBusy(true)
    setActionError(null)
    try {
      await booksApi.createRelationship(bookId, {
        ...buildRelationshipCreatePayload(selectedCharacter.id, relationshipDraft, relationshipChapter),
      })
      await refreshGraph()
      setRelationshipDraft(buildRelationshipDraft(relationshipChapter, relationshipDraft.counterpartId))
      setActiveTab("relationships")
    } catch {
      setActionError("Could not create the relationship.")
    } finally {
      setCreateRelationshipBusy(false)
    }
  }

  async function handleDeleteCharacter() {
    if (!selectedCharacter) return
    const confirmed = await confirm({
      title: `Delete ${selectedCharacter.name}?`,
      body: `Delete ${selectedCharacter.name} from this book? This is best for false positives and cannot be undone.`,
      confirmLabel: "Delete character",
      tone: "danger",
    })
    if (!confirmed) return

    setDeleting(true)
    setActionError(null)
    try {
      await booksApi.deleteCharacter(bookId, selectedCharacter.id)
      const remaining = chars.filter((char) => char.id !== selectedCharacter.id)
      setChars(remaining)
      setSelectedId(remaining[0]?.id || "")
      await refetchCharacterReview()
      await refreshGraph()
      setEditing(false)
      setCharacterMenuOpen(false)
    } catch {
      setActionError("Could not delete this character.")
    } finally {
      setDeleting(false)
    }
  }

  async function handlePartitionCharacter() {
    if (!selectedCharacter) return
    const input = await prompt({
      title: "Split character card",
      body: "Enter one character per line. Optional aliases: Name | alias one, alias two.",
      label: "Partition targets",
      initialValue: buildPartitionTargetSuggestion(selectedCharacter),
      confirmLabel: "Split character",
      multiline: true,
      validate: (value) => parsePartitionTargets(value).length >= 2 ? null : "Enter at least two distinct character names.",
    })
    if (!input) return

    const partitions = parsePartitionTargets(input)
    if (partitions.length < 2) {
      setActionError("Enter at least two distinct character names to split this card.")
      return
    }

    setPartitioning(true)
    setActionError(null)
    try {
      const response = await booksApi.partitionCharacter(bookId, selectedCharacter.id, { partitions })
      const refreshed = await booksApi.getCharacters(bookId)
      setChars(refreshed)
      setSelectedId(response.created[0] ?? refreshed[0]?.id ?? "")
      await refetchCharacterReview()
      setEditing(false)
      setWorkspaceMode("profile")
      setCharacterMenuOpen(false)
    } catch {
      setActionError("Could not split this character card.")
    } finally {
      setPartitioning(false)
    }
  }

  async function handleDemoteSelectedCharacter() {
    if (!selectedCharacter) return
    setSaving(true)
    setActionError(null)
    try {
      const response = await booksApi.demoteCharacter(bookId, selectedCharacter.id)
      const refreshed = await refreshCharacters()
      await refreshGraph()
      setWorkspaceMode("review")
      setSelectedId(refreshed[0]?.id ?? "")
      setNoteToast(`Moved ${selectedCharacter.name} back into review as candidate ${response.candidate_id.slice(0, 8)}.`)
      scheduleTimeout(() => setNoteToast(null), 2600)
    } catch {
      setActionError("Could not move this character back into the review queue.")
    } finally {
      setSaving(false)
    }
  }

  async function handleApproveCharacter() {
    if (!selectedCharacter) return
    setSaving(true)
    setActionError(null)
    try {
      const refreshed = await refreshCharactersAfter(() => booksApi.approveCharacter(bookId, selectedCharacter.id))
      setChars(refreshed)
      setSelectedId(selectedCharacter.id)
      setNoteToast(`${selectedCharacter.name} has been approved.`)
      scheduleTimeout(() => setNoteToast(null), 2600)
    } catch {
      setActionError("Could not approve this character.")
    } finally {
      setSaving(false)
    }
  }

  async function handleRejectCharacter() {
    if (!selectedCharacter) return
    setSaving(true)
    setActionError(null)
    try {
      const refreshed = await refreshCharactersAfter(() => booksApi.rejectCharacter(bookId, selectedCharacter.id))
      setChars(refreshed)
      setSelectedId(refreshed[0]?.id ?? "")
      setWorkspaceMode("profile")
      setNoteToast(`${selectedCharacter.name} has been rejected as noise.`)
      scheduleTimeout(() => setNoteToast(null), 2600)
    } catch {
      setActionError("Could not reject this character.")
    } finally {
      setSaving(false)
    }
  }

  async function handleToggleProtectedFromRepair() {
    if (!selectedCharacter || hasImplicitRepairProtection(selectedCharacter)) return
    setReviewNoteBusy(true)
    setActionError(null)
    try {
      const updated = await booksApi.updateCharacter(bookId, selectedCharacter.id, {
        protectedFromRepair: !selectedCharacter.analysis_metadata?.protected_from_repair,
        reviewNote: reviewNoteDraft.trim() || null,
      })
      setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
      if (workspaceMode === "repair") {
        await refetchRepairPreview()
      }
    } catch {
      setActionError("Could not update the repair protection flag.")
    } finally {
      setReviewNoteBusy(false)
    }
  }

  async function handleSaveReviewNote() {
    if (!selectedCharacter) return
    setReviewNoteBusy(true)
    setActionError(null)
    try {
      const updated = await booksApi.updateCharacter(bookId, selectedCharacter.id, {
        reviewNote: reviewNoteDraft.trim() || null,
        protectedFromRepair: selectedCharacter.analysis_metadata?.protected_from_repair ?? false,
      })
      setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
      setNoteToast(`Saved review note for ${updated.name}.`)
      scheduleTimeout(() => setNoteToast(null), 2200)
    } catch {
      setActionError("Could not save this review note.")
    } finally {
      setReviewNoteBusy(false)
    }
  }

  async function refreshCharactersAfter(action: () => Promise<unknown>) {
    await action()
    return refreshCharacters()
  }

  return {
    createBusy,
    createRelationshipBusy,
    deleting,
    graphOverrideBusy,
    handleApproveCharacter,
    handleCreateCharacter,
    handleCreateRelationship,
    handleDeleteCharacter,
    handleDemoteSelectedCharacter,
    handleGraphVisibilityOverride,
    handlePartitionCharacter,
    handleRejectCharacter,
    handleSaveCharacter,
    handleSaveReviewNote,
    handleToggleProtectedFromRepair,
    partitioning,
    reviewNoteBusy,
    saving,
  }
}
