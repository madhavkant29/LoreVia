import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import type { Book, WriterWorkspace } from "@/types/book"

type ManuscriptExportFormat = "pdf" | "docx" | "epub" | "vault"

type SaveWorkspace = (patch: Partial<WriterWorkspace>, options?: { silent?: boolean }) => Promise<void>

type UseManuscriptExportActionsArgs = {
  book: Book | null
  bookId: string
  compileFormat: ManuscriptExportFormat
  includeSceneMetadataOnExport: boolean
  includeTableOfContentsOnExport: boolean
  writerWorkspace: WriterWorkspace | null
  saveWorkspace: SaveWorkspace
  setExporting: Dispatch<SetStateAction<ManuscriptExportFormat | null>>
  setShowCompileDialog: Dispatch<SetStateAction<boolean>>
}

export function useManuscriptExportActions({
  book,
  bookId,
  compileFormat,
  includeSceneMetadataOnExport,
  includeTableOfContentsOnExport,
  saveWorkspace,
  setExporting,
  setShowCompileDialog,
  writerWorkspace,
}: UseManuscriptExportActionsArgs) {
  async function exportManuscript(format: ManuscriptExportFormat) {
    setExporting(format)
    try {
      const preset = writerWorkspace?.publishing.active_preset ?? "standard_manuscript"
      const blob = await booksApi.exportManuscript(bookId, format, preset, includeSceneMetadataOnExport, "serif", includeTableOfContentsOnExport)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      const extension = format === "vault" ? "zip" : format
      link.download = `${(book?.title || "lorevia").replace(/\s+/g, "-").toLowerCase()}-manuscript.${extension}`
      link.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(null)
    }
  }

  async function compileManuscript() {
    if (!writerWorkspace) return
    await saveWorkspace({ manuscript_front_matter: writerWorkspace.manuscript_front_matter }, { silent: true })
    setShowCompileDialog(false)
    await exportManuscript(compileFormat)
  }

  return {
    compileManuscript,
    exportManuscript,
  }
}
