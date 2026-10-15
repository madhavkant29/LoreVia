import { useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import type { WorldBuildingDocument } from "@/types/world-building"

import type { WorkspaceFocus } from "./WorldbuildingWorkspace.data"
import { getApiErrorDetail } from "./WorldbuildingWorkspace.helpers"

type Refetch = () => Promise<unknown>

interface UseWorldbuildingDocumentActionsArgs {
  bookId: string
  documentDraftDirty: boolean
  onSourcesChanged: () => void
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
  documentDraftDirty,
  onSourcesChanged,
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
  const lock = useRef(false)
  const queryClient = useQueryClient()
  const discardDraft = () => !documentDraftDirty || window.confirm("Discard unsaved edits to this source document?")
  function startNewDocument() {
    if (lock.current || !discardDraft()) return
    setSelectedDocumentId(null)
    setDraftTitle("")
    setDraftText("")
    setDocumentDraftDirty(false)
  }

  function selectDocument(documentId: string) {
    if (lock.current || documentId === selectedDocumentId || !discardDraft()) return
    setSelectedDocumentId(documentId)
    setDraftTitle(""); setDraftText("")
    setDocumentDraftDirty(false)
  }

  const saveDocument = async () => {
    if (lock.current || !draftText.trim()) return
    lock.current = true
    setSavingDocument(true)
    let saved = false
    try {
      if (selectedDocumentId) {
        const updated = await worldBuildingApi.updateDocument(bookId, selectedDocumentId, {
          title: draftTitle.trim() || selectedDocument?.title || "Worldbuilding Manuscript",
          text: draftText,
        })
        saved = true
        onSourcesChanged()
        queryClient.setQueryData([`worldbuilding:${bookId}:document:${updated.id}`], updated)
        queryClient.setQueryData<WorldBuildingDocument[]>([`worldbuilding:${bookId}:documents`], (current = []) => current.map((document) => document.id === updated.id ? updated : document))
        setDraftTitle(updated.title)
        setDraftText(updated.text)
        setDocumentDraftDirty(false)
        await refetchDocuments()
        setSelectedDocumentId(updated.id)
        setStatusMessage(`Saved ${updated.title}.`)
      } else {
        const created = await worldBuildingApi.uploadDocuments(bookId, {
          title: draftTitle.trim() || "Worldbuilding Manuscript",
          text: draftText,
        })
        const nextSelected = created[0]?.id ?? null
        if (!nextSelected) throw new Error("No source document was returned")
        saved = true
        onSourcesChanged()
        queryClient.setQueryData([`worldbuilding:${bookId}:document:${nextSelected}`], { ...created[0], text: draftText })
        queryClient.setQueryData<WorldBuildingDocument[]>([`worldbuilding:${bookId}:documents`], (current = []) => [...current, ...created])
        setDocumentDraftDirty(false)
        setSelectedDocumentId(nextSelected)
        await refetchDocuments()
        setStatusMessage(created.length ? `Created ${created[0].title}.` : "Created worldbuilding document.")
      }
      if (focus === "gap") {
        await runAnalysis()
      } else {
        await refetchElements()
      }
      await refetchUploadStats()
    } catch (error) {
      setStatusMessage(saved ? "The document was saved, but related data could not refresh. Refresh the workspace before making further changes." : `${getApiErrorDetail(error) ?? "Could not confirm the source save."} Your draft is retained. Check the source list before retrying a new document to avoid a duplicate.`)
    } finally {
      lock.current = false
      setSavingDocument(false)
    }
  }

  const uploadDocumentFiles = async () => {
    if (lock.current || !uploadFiles.length || !discardDraft()) return
    if (replaceCorpusOnUpload && !window.confirm("Replace all active canon sources with these files? Existing source content will no longer be available in this workspace. Keep a separate copy before continuing.")) return
    lock.current = true
    setUploadingFiles(true)
    let saved = false
    try {
      const created = await worldBuildingApi.uploadDocuments(bookId, {
        title: uploadTitle.trim() || undefined,
        files: uploadFiles,
        replaceExisting: replaceCorpusOnUpload,
      })
      if (!created.length) throw new Error("No source documents were returned")
      saved = true
      onSourcesChanged()
      queryClient.setQueryData<WorldBuildingDocument[]>([`worldbuilding:${bookId}:documents`], (current = []) => replaceCorpusOnUpload ? created : [...current, ...created])
      setUploadFiles([])
      setUploadTitle("")
      setReplaceCorpusOnUpload(false)
      setSelectedDocumentId(created[0]?.id ?? null)
      setDocumentDraftDirty(false)
      setDraftText(""); setDraftTitle("")
      await refetchDocuments()
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
      setStatusMessage(saved ? "The files were imported, but related data could not refresh. Refresh the source list before uploading again." : `${getApiErrorDetail(error) ?? "Could not confirm the import."} Your selected files are retained. Check the source list before retrying to avoid duplicates.`)
    } finally {
      lock.current = false
      setUploadingFiles(false)
    }
  }

  const deleteDocument = async () => {
    if (lock.current || !selectedDocumentId || !window.confirm(`Delete ${selectedDocument?.title || "this source document"}? This removes its canon content. Unsaved edits will also be discarded.`)) return
    lock.current = true
    setDeletingDocument(true)
    let deleted = false
    try {
      await worldBuildingApi.deleteDocument(bookId, selectedDocumentId)
      deleted = true
      onSourcesChanged()
      queryClient.setQueryData<WorldBuildingDocument[]>([`worldbuilding:${bookId}:documents`], (current = []) => current.filter((document) => document.id !== selectedDocumentId))
      setSelectedDocumentId(null)
      setDraftTitle(""); setDraftText("")
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
      setStatusMessage(deleted ? "The document was deleted, but related data could not refresh. Refresh the source list to check its current state." : getApiErrorDetail(error) ?? "Could not delete that worldbuilding document. Your draft is retained.")
    } finally {
      lock.current = false
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
