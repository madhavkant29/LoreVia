import axios from "axios"
import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { normalizeProcessingStatus } from "@/lib/utils/processingStatus"
import { clearQueuedManuscriptSave, enqueueManuscriptSave, isOfflineSaveError } from "@/lib/offline/manuscriptOutbox"
import type { Book, SaveState, WriterWorkspace } from "@/types/book"
import type { BookDraftMap } from "./manuscriptPage.helpers"
import type { SaveTarget } from "./manuscriptPage.constants"

type BookDraft = { title: string; text: string; html: string }
type SaveWorkspace = (patch: Partial<WriterWorkspace>, options?: { silent?: boolean }) => Promise<void>
type SetTargetSaveState = (target: SaveTarget, state: SaveState) => void
type SetTargetRetry = (target: SaveTarget, retry: (() => Promise<void>) | null) => void
type ParseChapterHeading = (rawValue: string, fallbackNumber: number, fallbackTitle: string) => {
  chapterNumber: number
  title: string
}

function newChapterMutationId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `chapter-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function chapterSaveError(error: unknown) {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  return typeof detail === "object" && detail !== null
    ? detail as { code?: string; message?: string; current_content_version?: number }
    : null
}

type UseManuscriptSaveActionsArgs = {
  activeChapterNumber: number
  autoReprocessEnabled: boolean
  book: Book | null
  bookDrafts: BookDraftMap
  bookId: string
  chapterTitle: string
  contentVersionByChapter: Record<number, number>
  html: string
  processingRetrying: boolean
  reprocessing: boolean
  reprocessingChapterNumber: number | null
  replaceExisting: boolean
  selectedChapter: number | null
  text: string
  writerWorkspace: WriterWorkspace | null
  clearDraftDirty: (chapterNumber: number) => void
  completeFindingEdit: () => Promise<void>
  loadBase: () => Promise<void>
  loadWorkspaceTree: () => Promise<void>
  markDraftDirty: (chapterNumber: number) => void
  parseChapterHeading: ParseChapterHeading
  refetchWriterWorkspace: () => Promise<unknown>
  refreshChapterVersionToken: (chapterNumber: number) => Promise<number>
  runAutomaticChecks: (chapterNumber: number, content: string) => Promise<void>
  saveWorkspace: SaveWorkspace
  setBook: Dispatch<SetStateAction<Book | null>>
  setBookDrafts: Dispatch<SetStateAction<BookDraftMap>>
  setChapterTitle: Dispatch<SetStateAction<string>>
  setContentVersionByChapter: Dispatch<SetStateAction<Record<number, number>>>
  setDraftChapterNumber: Dispatch<SetStateAction<number | null>>
  setProcessingRetrying: Dispatch<SetStateAction<boolean>>
  setReprocessing: Dispatch<SetStateAction<boolean>>
  setReprocessingChapterNumber: Dispatch<SetStateAction<number | null>>
  setSaving: Dispatch<SetStateAction<boolean>>
  setSelectedChapter: Dispatch<SetStateAction<number | null>>
  setShowReprocessConfirm: Dispatch<SetStateAction<boolean>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  setTargetRetry: SetTargetRetry
  setTargetSaveState: SetTargetSaveState
  setWriterWorkspace: Dispatch<SetStateAction<WriterWorkspace | null>>
}

export function useManuscriptSaveActions({
  activeChapterNumber,
  autoReprocessEnabled,
  book,
  bookDrafts,
  bookId,
  chapterTitle,
  clearDraftDirty,
  completeFindingEdit,
  contentVersionByChapter,
  html,
  loadBase,
  loadWorkspaceTree,
  markDraftDirty,
  parseChapterHeading,
  processingRetrying,
  refetchWriterWorkspace,
  refreshChapterVersionToken,
  reprocessing,
  reprocessingChapterNumber,
  runAutomaticChecks,
  saveWorkspace,
  selectedChapter,
  setBook,
  setBookDrafts,
  setChapterTitle,
  setContentVersionByChapter,
  setDraftChapterNumber,
  setProcessingRetrying,
  setReprocessing,
  setReprocessingChapterNumber,
  setSaving,
  setSelectedChapter,
  setShowReprocessConfirm,
  setStatusMessage,
  setTargetRetry,
  setTargetSaveState,
  setWriterWorkspace,
  text,
  writerWorkspace,
}: UseManuscriptSaveActionsArgs) {
  function markPendingManualReprocess(chapterNumber: number) {
    setWriterWorkspace((current) => {
      const base = current ?? writerWorkspace
      if (!base) return current
      const reprocess = base.reprocess ?? { auto_reprocess_enabled: false, pending_chapters: [] }
      return {
        ...base,
        reprocess: {
          ...reprocess,
          pending_chapters: Array.from(new Set([...(reprocess.pending_chapters ?? []), chapterNumber])),
        },
      }
    })
  }

  async function saveChapterDraft(chapterNumber: number, draft?: BookDraft) {
    const currentDraft = draft ?? bookDrafts[chapterNumber] ?? { title: chapterTitle, text, html }
    if (!currentDraft.text.trim()) return

    try {
      const result = await booksApi.saveChapterContent(bookId, chapterNumber, {
        text: currentDraft.text,
        sanitizedHtml: currentDraft.html,
        title: currentDraft.title.trim() || undefined,
        expectedContentVersion: contentVersionByChapter[chapterNumber] ?? 0,
        clientMutationId: newChapterMutationId(),
      })
      const importedChapter = result.chapter_number
      const nextContentVersion = result.content_version
      await clearQueuedManuscriptSave(bookId, chapterNumber, {
        title: currentDraft.title.trim() || `Chapter ${chapterNumber}`,
        text: currentDraft.text,
        html: currentDraft.html,
        expectedContentVersion: contentVersionByChapter[chapterNumber],
      }).catch(() => undefined)
      setSelectedChapter(importedChapter)
      if (typeof nextContentVersion === "number") {
        setContentVersionByChapter((current) => ({
          ...current,
          [importedChapter]: nextContentVersion,
        }))
      }
      clearDraftDirty(chapterNumber)
      clearDraftDirty(importedChapter)
      await loadWorkspaceTree()
      const shouldAutoRefresh = autoReprocessEnabled && result.story_memory_status !== "not_required"
      if (result.story_memory_status === "not_required") markPendingManualReprocess(importedChapter)
      if (!shouldAutoRefresh) await refetchWriterWorkspace()
      if (shouldAutoRefresh) await runAutomaticChecks(importedChapter, currentDraft.text)
      await completeFindingEdit()
      setStatusMessage(
        shouldAutoRefresh
          ? `Saved chapter ${importedChapter}. Story memory and Canon Guard refresh are queued.`
          : `Saved chapter ${importedChapter}. It needs manual reprocess to update story memory.`,
      )
    } catch (error) {
      const safeError = chapterSaveError(error)
      if (safeError?.code === "version_conflict" || (axios.isAxiosError(error) && error.response?.status === 409)) {
        await refreshChapterVersionToken(chapterNumber).catch(() => undefined)
        setStatusMessage(`Conflict - review needed. Chapter ${chapterNumber} changed in another session. Your local draft is still here.`)
        return
      }
      if (isOfflineSaveError(error)) {
        const queued = await enqueueManuscriptSave({
          bookId,
          chapterNumber,
          title: currentDraft.title.trim() || `Chapter ${chapterNumber}`,
          text: currentDraft.text,
          html: currentDraft.html,
          expectedContentVersion: contentVersionByChapter[chapterNumber],
        }).catch(() => null)
        markDraftDirty(chapterNumber)
        setStatusMessage(
          queued
            ? `Chapter ${chapterNumber} is saved offline and will sync when the connection returns.`
            : `Connection lost. This browser cannot store an offline copy, so keep this tab open and retry the save when you are online.`,
        )
        return
      }
      throw error
    }
  }

  async function saveCurrentChapter() {
    if (!text.trim()) return
    setSaving(true)
    setStatusMessage(null)
    try {
      const result = await booksApi.saveChapterContent(bookId, activeChapterNumber, {
        text,
        sanitizedHtml: html,
        title: chapterTitle.trim() || undefined,
        expectedContentVersion: selectedChapter !== null ? contentVersionByChapter[activeChapterNumber] ?? 1 : 0,
        clientMutationId: newChapterMutationId(),
      })
      await loadBase()
      const importedChapter = result.chapter_number
      const nextContentVersion = result.content_version
      await clearQueuedManuscriptSave(bookId, activeChapterNumber, {
        title: chapterTitle.trim() || `Chapter ${activeChapterNumber}`,
        text,
        html,
        expectedContentVersion: selectedChapter !== null
          ? contentVersionByChapter[activeChapterNumber]
          : undefined,
      }).catch(() => undefined)
      setSelectedChapter(importedChapter)
      clearDraftDirty(importedChapter)
      setBookDrafts((current) => ({
        ...current,
        [importedChapter]: { title: chapterTitle.trim() || `Chapter ${importedChapter}`, text, html },
      }))
      if (typeof nextContentVersion === "number") {
        setContentVersionByChapter((current) => ({
          ...current,
          [importedChapter]: nextContentVersion,
        }))
      }
      await loadWorkspaceTree()
      const shouldAutoRefresh = autoReprocessEnabled && result.story_memory_status !== "not_required"
      if (result.story_memory_status === "not_required") markPendingManualReprocess(importedChapter)
      if (!shouldAutoRefresh) await refetchWriterWorkspace()
      if (shouldAutoRefresh) await runAutomaticChecks(importedChapter, text)
      await completeFindingEdit()
      setStatusMessage(
        shouldAutoRefresh
          ? `Saved chapter ${importedChapter}. Story memory and Canon Guard refresh are queued.`
          : `Saved chapter ${importedChapter}. It needs manual reprocess to update story memory.`,
      )
    } catch (error) {
      const safeError = chapterSaveError(error)
      if ((safeError?.code === "version_conflict" || (axios.isAxiosError(error) && error.response?.status === 409)) && selectedChapter !== null) {
        await refreshChapterVersionToken(activeChapterNumber).catch(() => undefined)
        setStatusMessage(`Conflict - review needed. Chapter ${activeChapterNumber} changed in another session. Your local draft is still here.`)
      } else if (isOfflineSaveError(error)) {
        const queued = await enqueueManuscriptSave({
          bookId,
          chapterNumber: activeChapterNumber,
          title: chapterTitle.trim() || `Chapter ${activeChapterNumber}`,
          text,
          html,
          expectedContentVersion: selectedChapter !== null ? contentVersionByChapter[activeChapterNumber] : undefined,
        }).catch(() => null)
        markDraftDirty(activeChapterNumber)
        setStatusMessage(
          queued
            ? `Chapter ${activeChapterNumber} is saved offline and will sync when the connection returns.`
            : "Connection lost. This browser cannot store an offline copy, so keep this tab open and retry the save when you are online.",
        )
      } else {
        setStatusMessage(safeError?.message ? `${safeError.message} Your local draft is still here.` : "Save failed - action required. Your local draft is still here; retry or ask Support.")
      }
    } finally {
      setSaving(false)
    }
  }

  async function confirmReprocessManuscript() {
    if (!book || reprocessing) return
    setReprocessing(true)
    setStatusMessage(null)
    try {
      const result = await booksApi.reprocessManuscript(book.id)
      setShowReprocessConfirm(false)
      setStatusMessage(`Reprocessing started for ${result.chapters_queued} chapter${result.chapters_queued === 1 ? "" : "s"}. ${result.processed_words_reserved.toLocaleString()} processed words are reserved and will settle chapter by chapter.`)
      await loadBase()
    } catch {
      setStatusMessage("Reprocess failed. Check your processed-word allowance and try again.")
    } finally {
      setReprocessing(false)
    }
  }

  async function retryProcessing() {
    if (!book || processingRetrying) return
    setProcessingRetrying(true)
    setStatusMessage(null)
    try {
      const normalized = normalizeProcessingStatus(book.processing, book)
      const processing = normalized?.resumeAvailable
        ? await booksApi.continueProcessing(book.id)
        : await booksApi.retryProcessing(book.id)
      setBook((current) => current ? { ...current, status: "processing", processing } : current)
      setStatusMessage(normalized?.resumeAvailable ? "Processing continuation started." : "Processing retry started.")
      await loadBase()
    } catch {
      setStatusMessage("Processing retry is not available right now.")
    } finally {
      setProcessingRetrying(false)
    }
  }

  async function toggleAutoReprocess(enabled: boolean) {
    const currentReprocess = writerWorkspace?.reprocess ?? {
      auto_reprocess_enabled: true,
      pending_chapters: [],
    }
    await saveWorkspace({
      reprocess: {
        ...currentReprocess,
        auto_reprocess_enabled: enabled,
      },
    }, { silent: true })
    setStatusMessage(
      enabled
        ? "Auto reprocess edits is on."
        : "Auto reprocess edits is off. Open each edited chapter and click Reprocess to update story memory.",
    )
  }

  async function reprocessChapter(chapterNumber: number) {
    if (!book || reprocessingChapterNumber !== null) return
    setReprocessingChapterNumber(chapterNumber)
    setStatusMessage(null)
    try {
      await booksApi.reprocessChapter(book.id, chapterNumber)
      setWriterWorkspace((current) => current ? {
        ...current,
        reprocess: {
          ...(current.reprocess ?? { auto_reprocess_enabled: true, pending_chapters: [] }),
          pending_chapters: (current.reprocess?.pending_chapters ?? []).filter((item) => item !== chapterNumber),
          last_manual_chapter_number: chapterNumber,
          last_manual_chapter_started_at: new Date().toISOString(),
        },
      } : current)
      await refetchWriterWorkspace()
      await loadBase()
      setStatusMessage(`Chapter ${chapterNumber} reprocessing started. This uses tokens, not a book upload.`)
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 429) {
        setStatusMessage("Manual chapter reprocess token limit reached. Try again after your rolling window refreshes.")
      } else {
        setStatusMessage(`Chapter ${chapterNumber} reprocess failed. Try again later.`)
      }
    } finally {
      setReprocessingChapterNumber(null)
    }
  }

  async function handleChapterHeadingBlur(rawValue: string, fallbackNumber: number, fallbackTitle: string) {
    const parsed = parseChapterHeading(rawValue, fallbackNumber, fallbackTitle)
    const currentDraft = bookDrafts[fallbackNumber] ?? { title: fallbackTitle, text, html }
    const nextDraft = { ...currentDraft, title: parsed.title }

    setChapterTitle(parsed.title)
    setDraftChapterNumber(selectedChapter === null ? parsed.chapterNumber : null)
    setBookDrafts((current) => ({
      ...current,
      [parsed.chapterNumber]: {
        ...(current[parsed.chapterNumber] ?? nextDraft),
        title: parsed.title,
        text: selectedChapter === null ? text : current[parsed.chapterNumber]?.text ?? nextDraft.text,
        html: selectedChapter === null ? html : current[parsed.chapterNumber]?.html ?? nextDraft.html,
      },
    }))
    markDraftDirty(parsed.chapterNumber)

    const draftToPersist = selectedChapter === null
      ? { title: parsed.title, text, html }
      : { title: parsed.title, text: currentDraft.text, html: currentDraft.html }

    if (!draftToPersist.text.trim()) return

    setSaving(true)
    setTargetSaveState("chapter_title", "saving")
    setTargetRetry("chapter_title", null)
    try {
      await saveChapterDraft(parsed.chapterNumber, draftToPersist)
      setTargetSaveState("chapter_title", "saved")
    } catch {
      setTargetSaveState("chapter_title", "error")
      setTargetRetry("chapter_title", () => handleChapterHeadingBlur(rawValue, fallbackNumber, fallbackTitle))
      setStatusMessage("Could not save chapter title. Your local title is still kept here.")
    } finally {
      setSaving(false)
    }
  }

  async function saveFullBook() {
    const draftEntries = Object.entries(bookDrafts)
      .map(([chapterNumber, draft]) => [Number(chapterNumber), draft] as const)
      .filter(([, draft]) => draft.text.trim())
      .sort((a, b) => a[0] - b[0])
    if (!draftEntries.length) return

    setSaving(true)
    setStatusMessage(null)
    try {
      // Sequential saves are intentional: each saveChapterDraft calls setSelectedChapter,
      // loadWorkspaceTree, and runAutomaticChecks which must not overlap.
      for (const [chapterNumber, draft] of draftEntries) {
        await saveChapterDraft(chapterNumber, draft)
      }
      await loadBase()
      setStatusMessage(`Saved ${draftEntries.length} chapter${draftEntries.length === 1 ? "" : "s"} from the full-book editor.`)
    } catch {
      setStatusMessage("One of the chapter saves failed. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  return {
    confirmReprocessManuscript,
    handleChapterHeadingBlur,
    reprocessChapter,
    retryProcessing,
    saveChapterDraft,
    saveCurrentChapter,
    saveFullBook,
    toggleAutoReprocess,
  }
}
