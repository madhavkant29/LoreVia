import { worldBuildingApi } from "@/lib/api/worldBuilding"
import type { WorldBuildingDocument } from "@/types/world-building"

import type { WorkspaceFocus } from "./WorldbuildingWorkspace.data"
import { getApiErrorDetail } from "./WorldbuildingWorkspace.helpers"

type Refetch = () => Promise<unknown>

interface UseWorldbuildingDocumentActionsArgs {
  bookId: string
  draftText: string
  draftTitle: string
  focus: WorkspaceFocus
  replaceCorpusOnUpload: boolean
  selectedDocument: WorldBuildingDocument | null
  selectedDocumentId: string | null
  uploadFiles: File[]
  uploadTitle: string
  refetchDocuments: Refetch
  refetchElements: Refetch
  refetchSelectedDocument: Refetch
  refetchUploadStats: Refetch
  runAnalysis: Refetch
  setDeletingDocument: (value: boolean) => void
  setDocumentDraftDirty: (value: boolean) => void
  setDraftText: (value: string) => void
  setDraftTitle: (value: string) => void
  setReplaceCorpusOnUpload: (value: boolean) => void
  setSavingDocument: (value: boolean) => void
  setSelectedDocumentId: (value: string | null) => void
  setStatusMessage: (value: string | null) => void
  setUploadingFiles: (value: boolean) => void
  setUploadFiles: (value: File[]) => void
  setUploadTitle: (value: string) => void
}

export function useWorldbuildingDocumentActions({
  bookId,
  draftText,
  draftTitle,
  focus,
  replaceCorpusOnUpload,
  selectedDocument,
  selectedDocumentId,
  uploadFiles,
  uploadTitle,
  refetchDocuments,
  refetchElements,
  refetchSelectedDocument,
  refetchUploadStats,
  runAnalysis,
  setDeletingDocument,
  setDocumentDraftDirty,
  setDraftText,
  setDraftTitle,
  setReplaceCorpusOnUpload,
  setSavingDocument,
  setSelectedDocumentId,
  setStatusMessage,
  setUploadingFiles,
  setUploadFiles,
  setUploadTitle,
}: UseWorldbuildingDocumentActionsArgs) {
  function startNewDocument() {
    setSelectedDocumentId(null)
    setDraftTitle("")
    setDraftText("")
    setDocumentDraftDirty(false)
  }

  function selectDocument(documentId: string) {
    setSelectedDocumentId(documentId)
    setDocumentDraftDirty(false)
  }

  const saveDocument = async () => {
    if (!draftText.trim()) return
    setSavingDocument(true)
    try {
      if (selectedDocumentId) {
        const updated = await worldBuildingApi.updateDocument(bookId, selectedDocumentId, {
          title: draftTitle.trim() || selectedDocument?.title || "Worldbuilding Manuscript",
          text: draftText,
        })
        setDraftTitle(updated.title)
        setDraftText(updated.text)
        setDocumentDraftDirty(false)
        await refetchDocuments()
        setSelectedDocumentId(updated.id)
        await refetchSelectedDocument()
        setStatusMessage(`Saved ${updated.title}.`)
      } else {
        const created = await worldBuildingApi.uploadDocuments(bookId, {
          title: draftTitle.trim() || "Worldbuilding Manuscript",
          text: draftText,
        })
        const nextSelected = created[0]?.id ?? null
        setDocumentDraftDirty(false)
        await refetchDocuments()
        setSelectedDocumentId(nextSelected)
        setStatusMessage(created.length ? `Created ${created[0].title}.` : "Created worldbuilding document.")
      }
      if (focus === "gap") {
        await runAnalysis()
      } else {
        await refetchElements()
      }
      await refetchUploadStats()
    } catch (error) {
      setStatusMessage(getApiErrorDetail(error) ?? "Could not save that worldbuilding document.")
    } finally {
      setSavingDocument(false)
    }
  }

  const uploadDocumentFiles = async () => {
    if (!uploadFiles.length) return
    setUploadingFiles(true)
    try {
      const created = await worldBuildingApi.uploadDocuments(bookId, {
        title: uploadTitle.trim() || undefined,
        files: uploadFiles,
        replaceExisting: replaceCorpusOnUpload,
      })
      setUploadFiles([])
      setUploadTitle("")
      setReplaceCorpusOnUpload(false)
      await refetchDocuments()
      setSelectedDocumentId(created[0]?.id ?? null)
      setDocumentDraftDirty(false)
      if (focus === "gap") {
        await runAnalysis()
      } else {
        await refetchElements()
      }
      setStatusMessage(
        replaceCorpusOnUpload
          ? "Replaced the active world corpus and loaded the new documents."
          : `Added ${created.length} worldbuilding document${created.length === 1 ? "" : "s"} to the corpus.`
      )
      await refetchUploadStats()
    } catch (error) {
      setStatusMessage(getApiErrorDetail(error) ?? "Could not import the worldbuilding files.")
    } finally {
      setUploadingFiles(false)
    }
  }

  const deleteDocument = async () => {
    if (!selectedDocumentId) return
    setDeletingDocument(true)
    try {
      await worldBuildingApi.deleteDocument(bookId, selectedDocumentId)
      setSelectedDocumentId(null)
      setDocumentDraftDirty(false)
      await refetchDocuments()
      if (focus === "gap") {
        await runAnalysis()
      } else {
        await refetchElements()
      }
      setStatusMessage("Removed that worldbuilding document from the active corpus.")
      await refetchUploadStats()
    } catch (error) {
      setStatusMessage(getApiErrorDetail(error) ?? "Could not delete that worldbuilding document.")
    } finally {
      setDeletingDocument(false)
    }
  }

  return {
    deleteDocument,
    saveDocument,
    selectDocument,
    startNewDocument,
    uploadDocumentFiles,
  }
}
