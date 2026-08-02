import type { Character } from "@/types/character"
import type { MenuAction } from "./charactersPage.components"
import { isProtectedCharacter } from "./charactersPage.helpers"

type ExportingState = false | "character" | "bible" | null | undefined

type BuildPageMenuActionsArgs = {
  exporting: ExportingState
  isAuthorMode: boolean
  refreshingGraph: boolean
  onClosePageMenu: () => void
  onCreateCharacter: () => void
  onExportCharacterBible: (format: "md" | "pdf") => void
  onManualMerge: () => void
  onOpenDuplicateReview: () => void
  onOpenRepairWorkspace: () => void
  onOpenReviewQueue: () => void
  onRebuildGraph: () => void
  onResetFilters: () => void
}

export function buildPageMenuActions({
  exporting,
  isAuthorMode,
  refreshingGraph,
  onClosePageMenu,
  onCreateCharacter,
  onExportCharacterBible,
  onManualMerge,
  onOpenDuplicateReview,
  onOpenRepairWorkspace,
  onOpenReviewQueue,
  onRebuildGraph,
  onResetFilters,
}: BuildPageMenuActionsArgs): MenuAction[] {
  return [
    ...(isAuthorMode ? [{
      label: "Open add character",
      onClick: () => {
        onCreateCharacter()
        onClosePageMenu()
      },
    }] : []),
    ...(isAuthorMode ? [{ label: "Open review queue", onClick: onOpenReviewQueue }] : []),
    {
      label: exporting === "bible" ? "Exporting bible..." : "Export character bible",
      onClick: () => onExportCharacterBible("md"),
      disabled: exporting === "bible",
    },
    {
      label: exporting === "bible" ? "Exporting PDF..." : "Export as PDF",
      onClick: () => onExportCharacterBible("pdf"),
      disabled: exporting === "bible",
    },
    {
      label: "Review duplicate suggestions",
      onClick: () => {
        onOpenDuplicateReview()
        onClosePageMenu()
      },
    },
    ...(isAuthorMode ? [{ label: "Open repair workspace", onClick: onOpenRepairWorkspace }] : []),
    {
      label: "Open manual merge",
      onClick: () => {
        onManualMerge()
        onClosePageMenu()
      },
    },
    {
      label: refreshingGraph ? "Rebuilding graph..." : "Rebuild relationship graph",
      onClick: onRebuildGraph,
      disabled: refreshingGraph,
    },
    { label: "Reset filters", onClick: onResetFilters },
  ]
}

type BuildCharacterMenuActionsArgs = {
  character: Character | null
  deleting: boolean
  editing: boolean
  exporting: ExportingState
  isAuthorMode: boolean
  partitioning: boolean
  saving: boolean
  onCloseCharacterMenu: () => void
  onDeleteCharacter: () => void
  onDemoteSelectedCharacter: () => void
  onExportCharacter: (format: "pdf") => void
  onFindEvidence: () => void
  onManualMerge: (characterId: string) => void
  onOpenDuplicateReview: (characterId: string) => void
  onOpenReviewQueue: () => void
  onPartitionCharacter: () => void
  onSetEditing: (value: boolean | ((current: boolean) => boolean)) => void
  onToggleProtectedFromRepair: () => void
}

export function buildCharacterMenuActions({
  character,
  deleting,
  editing,
  exporting,
  isAuthorMode,
  partitioning,
  saving,
  onCloseCharacterMenu,
  onDeleteCharacter,
  onDemoteSelectedCharacter,
  onExportCharacter,
  onFindEvidence,
  onManualMerge,
  onOpenDuplicateReview,
  onOpenReviewQueue,
  onPartitionCharacter,
  onSetEditing,
  onToggleProtectedFromRepair,
}: BuildCharacterMenuActionsArgs): MenuAction[] {
  if (!character) return []

  return [
    {
      label: editing ? "Close edit details" : "Edit details",
      onClick: () => {
        onSetEditing((current) => !current)
        onCloseCharacterMenu()
      },
    },
    {
      label: "Add alias",
      onClick: () => {
        onSetEditing(true)
        onCloseCharacterMenu()
      },
    },
    {
      label: "Find mentions",
      onClick: () => {
        onFindEvidence()
        onCloseCharacterMenu()
      },
    },
    {
      label: "Find evidence",
      onClick: () => {
        onFindEvidence()
        onCloseCharacterMenu()
      },
    },
    {
      label: "Review duplicate candidates",
      onClick: () => {
        onOpenDuplicateReview(character.id)
        onCloseCharacterMenu()
      },
    },
    ...(isAuthorMode ? [{
      label: "Open review queue",
      onClick: () => {
        onOpenReviewQueue()
        onCloseCharacterMenu()
      },
    }] : []),
    {
      label: "Merge with another character",
      onClick: () => {
        onManualMerge(character.id)
        onCloseCharacterMenu()
      },
    },
    ...(isAuthorMode ? [{
      label: isProtectedCharacter(character) ? "Remove repair protection" : "Protect from repair",
      onClick: () => {
        onToggleProtectedFromRepair()
        onCloseCharacterMenu()
      },
    }] : []),
    ...(isAuthorMode ? [{
      label: saving ? "Moving to review..." : "Demote back to review",
      onClick: () => {
        onDemoteSelectedCharacter()
        onCloseCharacterMenu()
      },
      dividerBefore: true,
      disabled: saving,
    }] : []),
    {
      label: partitioning ? "Splitting character..." : "Split character card",
      onClick: onPartitionCharacter,
      disabled: partitioning || !isAuthorMode,
    },
    {
      label: exporting === "character" ? "Exporting character..." : "Export character PDF",
      onClick: () => onExportCharacter("pdf"),
      disabled: exporting === "character",
    },
    {
      label: deleting ? "Deleting..." : "Delete character",
      onClick: onDeleteCharacter,
      danger: true,
      disabled: deleting || !isAuthorMode,
    },
  ]
}
