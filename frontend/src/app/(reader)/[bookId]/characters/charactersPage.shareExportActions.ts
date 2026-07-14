import { useState } from "react"

import { booksApi } from "@/lib/api/books"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type { ConnectedRelationship } from "@/components/reader/CharacterProfileRightRail"
import type { Character } from "@/types/character"
import { downloadBlob } from "./charactersPage.helpers"
import { buildCharacterBibleExportFilename, buildCharacterCardExportFilename } from "./charactersPage.mutationPayloads"
import { buildCharacterWorkspaceNoteContent } from "./charactersPage.navigation"

type UseCharacterShareExportActionsArgs = {
  bookId: string
  bookTitle?: string | null
  scheduleTimeout: (callback: () => void, delay: number) => void
  selectedCharacter: Character | null
  selectedConnections: ConnectedRelationship[]
  setActionError: (value: string | null) => void
  setCharacterMenuOpen: (value: boolean) => void
  setNoteToast: (value: string | null) => void
  setPageMenuOpen: (value: boolean) => void
}

export function useCharacterShareExportActions({
  bookId,
  bookTitle,
  scheduleTimeout,
  selectedCharacter,
  selectedConnections,
  setActionError,
  setCharacterMenuOpen,
  setNoteToast,
  setPageMenuOpen,
}: UseCharacterShareExportActionsArgs) {
  const [shareState, setShareState] = useState<"idle" | "copied" | "error">("idle")
  const [exporting, setExporting] = useState<false | "character" | "bible">()

  async function handleShareCharacter() {
    if (!selectedCharacter) return
    try {
      const response = await booksApi.shareCharacter(bookId, selectedCharacter.id)
      const shareUrl = `${window.location.origin}${response.share_url}`
      await navigator.clipboard.writeText(shareUrl)
      setShareState("copied")
      scheduleTimeout(() => setShareState("idle"), 2200)
    } catch {
      setShareState("error")
      scheduleTimeout(() => setShareState("idle"), 2200)
    }
  }

  async function handleExportCharacter(format: "pdf" | "md" | "docx" = "pdf") {
    if (!selectedCharacter) return
    setExporting("character")
    try {
      const blob = await booksApi.exportCharacterCard(bookId, selectedCharacter.id, format)
      downloadBlob(blob, buildCharacterCardExportFilename(bookTitle, selectedCharacter.name, format))
      setCharacterMenuOpen(false)
    } finally {
      setExporting(false)
    }
  }

  async function handleExportCharacterBible(format: "pdf" | "md" | "docx" = "md") {
    setExporting("bible")
    try {
      const blob = await booksApi.exportCharacterBible(bookId, format)
      downloadBlob(blob, buildCharacterBibleExportFilename(bookTitle, format))
      setPageMenuOpen(false)
    } finally {
      setExporting(false)
    }
  }

  async function saveCharacterWorkspaceNote() {
    if (!selectedCharacter) return
    setActionError(null)
    try {
      await saveContextualVaultNote({
        bookId,
        title: selectedCharacter.name,
        content: buildCharacterWorkspaceNoteContent(selectedCharacter, selectedConnections),
        context: "characters",
        folderSegments: [selectedCharacter.name],
      })
      setNoteToast(`Saved ${selectedCharacter.name} to Characters.`)
      scheduleTimeout(() => setNoteToast(null), 2400)
    } catch {
      setActionError("Could not save this character to the notes workspace.")
    }
  }

  return {
    exporting,
    handleExportCharacter,
    handleExportCharacterBible,
    handleShareCharacter,
    saveCharacterWorkspaceNote,
    shareState,
  }
}
