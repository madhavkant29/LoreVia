"use client"

import axios from "axios"
import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import type React from "react"

import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { authApi } from "@/lib/api/auth"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { capture, captureTiming } from "@/lib/analytics/posthog"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { GENRE_TAGS } from "@/lib/constants/genreTags"
import { asQueryKey, bookCacheKey, booksSelectorCacheKey, booksSeriesCacheKey, booksStatsCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { useBookModeStore } from "@/lib/stores/bookModeStore"
import type { BookMode } from "@/lib/stores/bookModeStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { normalizeProcessingStatus } from "@/lib/utils/processingStatus"
import {
  BOOK_UPLOAD_MAX_BYTES,
  MANUSCRIPT_IMPORT_ACCEPT,
  NOVEL_UPLOAD_ACCEPT,
  SCREENPLAY_UPLOAD_ACCEPT,
  validateCoverFile,
  validateManuscriptFile,
  validateManuscriptFiles,
} from "@/lib/validation/manuscriptUpload"
import type { Book, BookSelector, ChapterConsistencyReport, PaginatedSeries, UserStats } from "@/types/book"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"
import { useUploadWizardState } from "./useUploadWizardState"
import { useUploadWorkflow } from "./useUploadWorkflow"
import { normalizeTag, tagSimilarity } from "./uploadUtils"

const MAX_TAGS = 8
const TAG_SUGGESTION_LIMIT = 18

function getApiErrorDetail(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === "string" && detail.trim()) return detail
    if (typeof detail?.message === "string" && detail.message.trim()) return detail.message
    if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
      return "The upload timed out before it finished. Check your connection and try again."
    }
    if (!error.response) {
      return "We couldn't reach LoreVia. Check your connection and try again."
    }
    if (error.response.status === 413) {
      return "This file is larger than the upload limit. Export a smaller file and try again."
    }
    if (error.response.status === 403) {
      return "Your account doesn't have access to this authoring feature yet."
    }
    if (error.response.status >= 500) {
      return "LoreVia hit a problem while processing your request. Please try again in a moment."
    }
  }
  if (error instanceof Error && error.message.trim()) return error.message
  return null
}

function pastedChapterDraftKey(userId: string, bookId: string) {
  return `lorevia:add-chapter-draft:${userId}:${bookId}`
}

function chapterSaveMutationId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `chapter-save-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

type Options = {
  onClose: () => void
  initialMode: BookMode
  initialExistingBookId: string
  presentation: "modal" | "inline"
}

export function useUploadModalController({ onClose, initialMode, initialExistingBookId, presentation }: Options) {
  const router = useRouter()
  const wizard = useUploadWizardState(initialMode, initialExistingBookId)
  const {
    title,
    author, setAuthor,
    authorManuallyEdited,
    mode, setMode,
    startEmpty,
    selectedTags, setSelectedTags,
    customTag,
    selectedSeriesIds, setSelectedSeriesIds,
    existingBookId, setExistingBookId,
    existingBookMenuOpen, setExistingBookMenuOpen,
    chapterSource, setChapterSource,
    chapterNumber, setChapterNumber,
    chapterNumberDirty, setChapterNumberDirty,
    chapterTitle, setChapterTitle,
    chapterText, setChapterText,
    replaceExisting, setReplaceExisting,
    splitIntoChapters, setSplitIntoChapters,
    chunkLongDocuments, setChunkLongDocuments,
    files, setFiles,
    workType, setWorkType,
    workTypeDirty,
    autoExtractCover, setAutoExtractCover,
    preserveChapterNumbers, setPreserveChapterNumbers,
    preserveSourceChapters, setPreserveSourceChapters,
    coverFile, setCoverFile,
    advancedSettingsOpen, setAdvancedSettingsOpen,
    usernameInput, setUsernameInput,
    importPreview, setImportPreview,
    dismissPreview, setDismissPreview,
    importAsSingle, setImportAsSingle,
    showEditor, setShowEditor,
  } = wizard
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [settingUsername, setSettingUsername] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStage, setUploadStage] = useState<"idle" | "uploading" | "processing">("idle")
  const [processingBookId, setProcessingBookId] = useState<string | null>(null)
  const [processingRetrying, setProcessingRetrying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [postImportReview, setPostImportReview] = useState<EditorialReview | null>(null)
  const [postImportPassages, setPostImportPassages] = useState<EditorialReviewPassage[]>([])
  const [postImportSuggestions, setPostImportSuggestions] = useState<AdvisorSuggestion[]>([])
  const [postImportThreads, setPostImportThreads] = useState<PlotThread[]>([])
  const [postImportSynopsis, setPostImportSynopsis] = useState<ManuscriptSynopsis | null>(null)
  const [chapterReports, setChapterReports] = useState<ChapterConsistencyReport[]>([])
  const [reportReady, setReportReady] = useState<{ bookId: string; chapterNum?: number; text: string } | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const coverInputRef = useRef<HTMLInputElement>(null)
  const existingBookMenuRef = useRef<HTMLDivElement>(null)
  const uploadStartedAtRef = useRef<number | null>(null)
  const processingReadyCapturedRef = useRef(false)
  const confirm = useConfirmDialog()
  const { theme } = usePreferencesStore()
  const user = useAuthStore((state) => state.user)
  const canUploadAuthorMode = canUseAuthorFeatures(user?.tier)
  const setBookMode = useBookModeStore((state) => state.setMode)
  const isDark = theme === "dark"
  const { data: paginatedSeries } = useQuery<PaginatedSeries>({
    queryKey: asQueryKey(booksSeriesCacheKey()),
    queryFn: () => booksApi.listSeries(),
  })
  const series = paginatedSeries?.items ?? []

  const {
    data: books = [],
    refetch: refetchBooks,
  } = useQuery<BookSelector[]>({
    queryKey: asQueryKey(booksSelectorCacheKey(true)),
    queryFn: () => booksApi.listSelector(true),
  })

  const { data: uploadStats = null } = useQuery<UserStats | null>({
    queryKey: asQueryKey(booksStatsCacheKey()),
    queryFn: () => booksApi.getStats(),
  })

  const { data: processingBook = null } = useQuery<Book | null>({
    queryKey: processingBookId ? asQueryKey(bookCacheKey(processingBookId, "detail")) : ["upload:processing:none"],
    queryFn: () => booksApi.get(processingBookId as string),
    enabled: Boolean(processingBookId),
    refetchInterval: (query) => {
      const currentBook = query.state.data as Book | null | undefined
      const canPoll = typeof document === "undefined" || document.visibilityState === "visible"
      return canPoll && currentBook && currentBook.status !== "ready" && currentBook.status !== "failed" ? 4_000 : false
    },
    refetchIntervalInBackground: false,
  })

  const { fetchPreview, loadPostImportReview, resetImportFeedback } = useUploadWorkflow({
    files,
    workType,
    setError,
    setPreviewLoading,
    setImportPreview,
    setDismissPreview,
    setPostImportReview,
    setPostImportPassages,
    setPostImportSuggestions,
    setPostImportThreads,
    setPostImportSynopsis,
    setChapterReports,
    setReportReady,
    getApiErrorDetail,
  })

  const infoButtonClass = `inline-flex h-4 w-4 items-center justify-center rounded-full border text-3xs font-semibold leading-none transition ${
    isDark
      ? "border-white/20 text-slate-300 hover:border-white/40 hover:bg-white/10 hover:text-white"
      : "border-stone-300 text-stone-500 hover:border-stone-400 hover:bg-stone-100 hover:text-stone-700"
  }`
  const visibility = "private" as const
  const genre = selectedTags.join(", ")
  const trimmedCustomTag = customTag.trim()
  const shouldShowTagSuggestions = trimmedCustomTag.length >= 2
  const suggestedTags = GENRE_TAGS
    .filter((tag) => !selectedTags.includes(tag))
    .filter((tag) => (shouldShowTagSuggestions ? tagSimilarity(tag, trimmedCustomTag) >= 0.34 : false))
    .sort((a, b) => tagSimilarity(b, trimmedCustomTag) - tagSimilarity(a, trimmedCustomTag))
    .slice(0, TAG_SUGGESTION_LIMIT)
  const existingAuthorBooks = books.filter((book) => book.mode === "author" && !book.hidden_at)
  const selectedExistingBook = existingAuthorBooks.find((book) => book.id === existingBookId) ?? null
  const existingBookSelectLabel = selectedExistingBook?.title ?? "Create a new upload"
  const isManagingExisting = mode === "author" && !!existingBookId
  const effectiveWorkType = isManagingExisting ? (selectedExistingBook?.work_type ?? workType) : workType
  const needsUsername = mode === "author" && !user?.username
  const hasChapterText = chapterText.trim().length > 0
  const hasChapterFiles = files.length > 0
  const canSubmitExistingImport = chapterSource === "paste" ? hasChapterText : hasChapterFiles
  useEffect(() => {
    setMode(initialMode)
  }, [initialMode, setMode])

  useEffect(() => {
    if (!canUploadAuthorMode && mode === "author") {
      setMode("reader")
    }
  }, [canUploadAuthorMode, mode, setMode])

  useEffect(() => {
    setExistingBookId(initialExistingBookId)
  }, [initialExistingBookId, setExistingBookId])

  useEffect(() => {
    setChapterNumberDirty(false)
  }, [initialExistingBookId, setChapterNumberDirty])

  useEffect(() => {
    resetImportFeedback()
  }, [chapterSource, existingBookId, resetImportFeedback])

  useEffect(() => {
    if (!isManagingExisting || chapterSource !== "paste" || !user?.id) return
    try {
      const raw = window.localStorage.getItem(pastedChapterDraftKey(user.id, existingBookId))
      if (!raw || chapterText.trim()) return
      const draft = JSON.parse(raw) as { chapterNumber?: string; chapterTitle?: string; chapterText?: string }
      if (draft.chapterNumber) setChapterNumber(draft.chapterNumber)
      if (draft.chapterTitle) setChapterTitle(draft.chapterTitle)
      if (draft.chapterText) setChapterText(draft.chapterText)
    } catch {
      // Local recovery is best effort; the form remains usable when storage is unavailable.
    }
  }, [
    chapterSource,
    chapterText,
    existingBookId,
    isManagingExisting,
    setChapterNumber,
    setChapterText,
    setChapterTitle,
    user?.id,
  ])

  useEffect(() => {
    if (!isManagingExisting || chapterSource !== "paste" || !user?.id || !chapterText.trim()) return
    try {
      window.localStorage.setItem(
        pastedChapterDraftKey(user.id, existingBookId),
        JSON.stringify({ chapterNumber, chapterTitle, chapterText, savedAt: new Date().toISOString() }),
      )
    } catch {
      // The save request still preserves the text in component state.
    }
  }, [chapterNumber, chapterSource, chapterText, chapterTitle, existingBookId, isManagingExisting, user?.id])

  // Set autoExtractCover based on file type: enabled by default for PDFs
  useEffect(() => {
    if (files.length === 0) return
    const primaryFile = files[0]
    const isPdf = primaryFile.name.toLowerCase().endsWith(".pdf")
    setAutoExtractCover(isPdf)
    if (!workTypeDirty) {
      const lowerName = primaryFile.name.toLowerCase()
      if (lowerName.endsWith(".fountain") || lowerName.endsWith(".screenplay") || lowerName.endsWith(".script")) {
        setWorkType("screenplay")
      }
    }
    setImportPreview(null)
    setDismissPreview(false)
    setImportAsSingle(false)
  }, [
    files,
    setAutoExtractCover,
    setDismissPreview,
    setImportAsSingle,
    setImportPreview,
    setWorkType,
    workTypeDirty,
  ])

  useEffect(() => {
    if (!processingBookId) return
    if (!processingBook) return
    if (processingBook.status !== "ready" && processingBook.status !== "failed") return
    setUploadStage("idle")
    setUploading(false)
    setProcessingBookId(null)
    if (processingBook.status === "ready") {
      if (!processingReadyCapturedRef.current) {
        processingReadyCapturedRef.current = true
        captureTiming("processing_ready_ms", uploadStartedAtRef.current ?? 0, {
          book_id: processingBook.id,
          route: "upload_modal",
        })
      }
      capture("processing_completed", {
        book_id: processingBook.id,
        mode: processingBook.mode,
        chapter_count: processingBook.total_chapters,
      })
      const target = `/${processingBook.id}?activation=1` as Route
      const timer = setTimeout(() => {
        onClose()
        router.push(target)
      }, 600)
      return () => clearTimeout(timer)
    }
    capture("processing_failed", { book_id: processingBook.id, mode: processingBook.mode })
  }, [onClose, processingBook, processingBookId, router])

  // Default new author-mode uploads to the current public username.
  useEffect(() => {
    if (mode === "author" && !isManagingExisting && !authorManuallyEdited && !author) {
      const preferred = user?.username
      if (preferred) setAuthor(preferred)
    }
  }, [author, authorManuallyEdited, isManagingExisting, mode, setAuthor, user?.username])

  async function handleSetUsername() {
    if (!usernameInput.trim()) return
    setSettingUsername(true)
    setUsernameError(null)
    try {
      const updatedUser = await authApi.setUsername(usernameInput.trim())
      useAuthStore.getState().setUser(updatedUser)
      setUsernameInput("")
    } catch {
      setUsernameError("Username already taken or invalid")
    } finally {
      setSettingUsername(false)
    }
  }

  const addTag = (rawTag: string) => {
    const tag = normalizeTag(rawTag)
    if (!tag) return
    setSelectedTags((current) => {
      if (current.includes(tag) || current.length >= MAX_TAGS) return current
      return [...current, tag]
    })
  }

  const removeTag = (tagToRemove: string) => {
    setSelectedTags((current) => current.filter((tag) => tag !== tagToRemove))
  }

  const toggleSeries = (seriesId: string) => {
    setSelectedSeriesIds((current) =>
      current.includes(seriesId)
        ? current.filter((item) => item !== seriesId)
        : [...current, seriesId]
    )
  }

  useEffect(() => {
    if (!isManagingExisting || replaceExisting || chapterNumberDirty) return
    const nextChapter = (selectedExistingBook?.total_chapters ?? 0) + 1
    if (nextChapter > 0) {
      setChapterNumber(String(nextChapter))
    }
  }, [
    chapterNumberDirty,
    isManagingExisting,
    replaceExisting,
    selectedExistingBook,
    setChapterNumber,
  ])

  useEffect(() => {
    if (!isManagingExisting || !selectedExistingBook) return
    setWorkType(selectedExistingBook.work_type)
  }, [isManagingExisting, selectedExistingBook, setWorkType])

  useEffect(() => {
    if (!existingBookMenuOpen) return
    const handlePointerDown = (event: MouseEvent) => {
      if (!existingBookMenuRef.current?.contains(event.target as Node)) {
        setExistingBookMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handlePointerDown)
    return () => document.removeEventListener("mousedown", handlePointerDown)
  }, [existingBookMenuOpen, setExistingBookMenuOpen])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const workTypeForValidation = effectiveWorkType === "screenplay" ? "screenplay" : "novel"
    if (isManagingExisting && !canSubmitExistingImport) {
      setError(chapterSource === "paste" ? "Paste a chapter before processing it." : "Please select a chapter file.")
      return
    }
    if (isManagingExisting && chapterSource !== "paste") {
      const fileError = validateManuscriptFiles(files, { workType: workTypeForValidation })
      if (fileError) {
        setError(fileError)
        return
      }
    }
    if (!isManagingExisting && !startEmpty) {
      const fileError = files[0]
        ? validateManuscriptFile(files[0], { workType: workTypeForValidation, maxBytes: BOOK_UPLOAD_MAX_BYTES })
        : "Please select at least one file"
      if (fileError) {
        setError(fileError)
        return
      }
    }
    if (!autoExtractCover && coverFile) {
      const coverError = validateCoverFile(coverFile)
      if (coverError) {
        setError(coverError)
        return
      }
    }

    setUploading(true)
    setUploadProgress(0)
    setUploadStage("uploading")
    uploadStartedAtRef.current = typeof performance !== "undefined" ? performance.now() : 0
    processingReadyCapturedRef.current = false
    capture("upload_started", {
      mode,
      kind: isManagingExisting ? "manuscript_import" : startEmpty ? "empty_project" : "new_upload",
      work_type: effectiveWorkType,
    })
    resetImportFeedback()
    let startedProcessing = false
    try {
      let bookId: string | null = null
      if (isManagingExisting) {
        const isPasteImport = chapterSource === "paste"
        if (isPasteImport) {
          const targetChapter = Number.parseInt(chapterNumber, 10)
          if (!Number.isFinite(targetChapter) || targetChapter < 1) {
            setError("Enter a valid chapter number before saving.")
            setUploading(false)
            setUploadStage("idle")
            return
          }
          let expectedContentVersion = 0
          if (replaceExisting) {
            const currentChapter = await readerApi.getChapter(existingBookId, targetChapter)
            expectedContentVersion = currentChapter.content_version ?? 1
          }
          await booksApi.saveChapterContent(existingBookId, targetChapter, {
            title: chapterTitle.trim() || undefined,
            text: chapterText.trim(),
            expectedContentVersion,
            clientMutationId: chapterSaveMutationId(),
          })
          bookId = existingBookId
          captureTiming("upload_first_result_ms", uploadStartedAtRef.current ?? 0, {
            mode: "author",
            kind: "single_chapter_paste",
          })
          setBookMode(existingBookId, "author")
          capture("book_uploaded", {
            mode: "author",
            kind: "single_chapter_paste",
            work_type: effectiveWorkType,
            file_count: 0,
            chapter_source: chapterSource,
            replace_existing: replaceExisting,
            split_into_chapters: false,
            chunk_long_documents: false,
          })
          setChapterReports([])
          if (user?.id) {
            try {
              window.localStorage.removeItem(pastedChapterDraftKey(user.id, existingBookId))
            } catch {
              // The server save is already confirmed.
            }
          }
          try {
            await loadPostImportReview(existingBookId, targetChapter, chapterText.trim())
          } catch {
            setError("Chapter saved, but the inline continuity review could not be loaded.")
          }
          setUploadStage("idle")
          setUploadProgress(100)
          await refetchBooks()
          onClose()
          router.push(`/${existingBookId}/manuscript?chapter=${targetChapter}`)
          return
        }
        const response = await booksApi.importManuscript(existingBookId, {
          chapterNumber: chapterNumber ? parseInt(chapterNumber) : undefined,
          replaceExisting,
          splitIntoChapters,
          chunkLongDocuments,
          workType: effectiveWorkType,
          files,
          onProgress: (completed, total) => {
            setUploadStage("processing")
            const percent = total > 0 ? Math.round((completed / total) * 100) : 0
            setUploadProgress(Math.min(95, Math.max(0, percent)))
          },
        })
        bookId = response.book_id
        captureTiming("upload_first_result_ms", uploadStartedAtRef.current ?? 0, {
          mode: "author",
          kind: isPasteImport ? "single_chapter_paste" : "manuscript_import",
        })
        setBookMode(response.book_id, "author")
        capture("book_uploaded", {
          mode: "author",
          kind: isPasteImport ? "single_chapter_paste" : "manuscript_import",
          work_type: effectiveWorkType,
          file_count: isPasteImport ? 0 : files.length,
          chapter_source: chapterSource,
          replace_existing: replaceExisting,
          split_into_chapters: splitIntoChapters,
          chunk_long_documents: chunkLongDocuments,
        })
        setChapterReports(response.chapter_reports ?? [])
        if (isPasteImport && user?.id) {
          try {
            window.localStorage.removeItem(pastedChapterDraftKey(user.id, existingBookId))
          } catch {
            // The server import is already confirmed.
          }
        }
        const importedChapter = response.imported_chapters[0]
        if (importedChapter) {
          try {
            if (isPasteImport && chapterText.trim()) {
              await loadPostImportReview(response.book_id, importedChapter, chapterText.trim())
            } else {
              const chapterData = await readerApi.getChapter(response.book_id, importedChapter)
              const recoveredText = chapterData.text_content || ""
              await loadPostImportReview(response.book_id, importedChapter, recoveredText)
            }
          } catch {
            setError("Chapter imported, but the inline continuity review could not be loaded.")
          }
        }
        setUploadStage("processing")
        setUploadProgress(100)
        await refetchBooks()
        setProcessingBookId(response.book_id)
        return
      } else if (startEmpty) {
        const response = await booksApi.createEmptyProject({
          title: title.trim(),
          author: author || null,
          genre: genre || null,
          work_type: workType,
          series_ids: selectedSeriesIds.length > 0 ? selectedSeriesIds : null,
        })
        bookId = response.book_id
        captureTiming("upload_first_result_ms", uploadStartedAtRef.current ?? 0, { mode, kind: "empty_project" })
        setBookMode(response.book_id, mode)
        capture("book_uploaded", {
          mode,
          kind: "empty_project",
          work_type: workType,
          in_series: selectedSeriesIds.length > 0,
        })
      } else {
        const primaryFile = files[0]
        const filename = (primaryFile?.name || "").toLowerCase()
        const effectivePreserve = importAsSingle ? false : preserveChapterNumbers
        const format = filename.endsWith(".pdf") ? "pdf" : filename.endsWith(".epub") ? "epub" : "other"
        const response = await booksApi.upload(primaryFile, title, genre || undefined, author || undefined, {
          visibility,
          seriesIds: selectedSeriesIds,
          autoExtractCover,
          preserveChapterNumbers: effectivePreserve,
          preserveSourceChapters,
          forceSingleManuscript: importAsSingle,
          workType,
          coverFile: autoExtractCover ? null : coverFile,
          mode,
          onProgress: (percent) => {
            setUploadProgress(percent)
          },
        })
        bookId = typeof response?.book_id === "string" ? response.book_id : null
        captureTiming("upload_first_result_ms", uploadStartedAtRef.current ?? 0, { mode, kind: "new_upload" })
        if (bookId) setBookMode(bookId, mode)
        capture("book_uploaded", {
          mode,
          kind: "new_upload",
          format,
          work_type: workType,
          has_cover_file: Boolean(coverFile) && !autoExtractCover,
          preserve_chapter_numbers: preserveChapterNumbers,
          preserve_source_chapters: preserveSourceChapters,
          tag_count: selectedTags.length,
          in_series: selectedSeriesIds.length > 0,
        })
      }
      setUploadProgress(100)
      if (!bookId) {
        onClose()
        return
      }
      if (!isManagingExisting) {
        await refetchBooks()
        onClose()
        return
      }
      setUploadStage("processing")
      startedProcessing = true
      setProcessingBookId(bookId)
    } catch (error) {
      capture("upload_failed", {
        mode,
        kind: isManagingExisting ? "manuscript_import" : startEmpty ? "empty_project" : "new_upload",
        work_type: effectiveWorkType,
      })
      setError(getApiErrorDetail(error) ?? "Upload failed. Please try again.")
      setProcessingBookId(null)
    } finally {
      setUploading(false)
      if (!startedProcessing) {
        setUploadStage("idle")
      }
    }
  }

  const isInline = presentation === "inline"
  const isScreenplayWorkspace = effectiveWorkType === "screenplay"
  const storyUnitLabel = isScreenplayWorkspace ? "scene" : "chapter"
  const storyUnitLabelTitle = isScreenplayWorkspace ? "Scene" : "Chapter"
  const newUploadAccept = isScreenplayWorkspace ? SCREENPLAY_UPLOAD_ACCEPT : NOVEL_UPLOAD_ACCEPT

  const handleFilesSelected = (selectedFiles: File[]) => {
    const workTypeForValidation = isScreenplayWorkspace ? "screenplay" : "novel"
    const validationError = isManagingExisting
      ? validateManuscriptFiles(selectedFiles, { workType: workTypeForValidation })
      : selectedFiles[0]
        ? validateManuscriptFile(selectedFiles[0], {
            workType: workTypeForValidation,
            maxBytes: BOOK_UPLOAD_MAX_BYTES,
          })
        : "Please select at least one file"
    if (validationError) {
      setError(validationError)
      setFiles([])
      return
    }
    setError(null)
    setFiles(selectedFiles)
  }

  const handleCoverSelected = (file: File | null) => {
    if (!file) {
      setCoverFile(null)
      return
    }
    const validationError = validateCoverFile(file)
    if (validationError) {
      setError(validationError)
      return
    }
    setError(null)
    setCoverFile(file)
  }
  const primaryFile = files[0] ?? null
  const chapterUploadHelp = isScreenplayWorkspace
    ? "Upload a screenplay PDF, Fountain, TXT, or Markdown script segment. LoreVia will turn scenes into synthetic chapters for the rest of the pipeline."
    : "Click to select a chapter file. Use PDF, EPUB, DOCX, TXT, or Markdown."
  const processingSummary = processingBook?.processing
    ? normalizeProcessingStatus(processingBook.processing, processingBook)
    : null
  async function retryProcessing() {
    if (!processingBookId) return
    setProcessingRetrying(true)
    setError(null)
    try {
      if (processingSummary?.resumeAvailable) {
        await booksApi.continueProcessing(processingBookId)
      } else {
        await booksApi.retryProcessing(processingBookId)
      }
      await refetchBooks()
    } catch (retryError) {
      setError(getApiErrorDetail(retryError) ?? "Processing could not be restarted. Please try again.")
    } finally {
      setProcessingRetrying(false)
    }
  }
  const uploadLimitCopy = uploadStats
    ? `${(uploadStats.private.active_analyzed_words ?? 0).toLocaleString()}/${(uploadStats.private.active_word_limit ?? 0).toLocaleString()} active words | ${(uploadStats.private.monthly_processed_words ?? 0).toLocaleString()}/${(uploadStats.private.monthly_processed_word_limit ?? 0).toLocaleString()} processed this month | ${((uploadStats.private.source_storage_bytes ?? 0) / 1024 ** 3).toFixed(1)}/${((uploadStats.private.source_storage_limit_bytes ?? 0) / 1024 ** 3).toFixed(0)} GB source storage${uploadStats.private.allowances_enforced ? "" : " (reporting only)"}.`
    : null
  const primaryActionDisabled =
    uploading ||
    needsUsername ||
    (isManagingExisting ? !canSubmitExistingImport : startEmpty ? !title.trim() : importPreview && !dismissPreview ? true : files.length === 0)
  const primaryActionLabel = uploading
    ? uploadStage === "uploading"
      ? isManagingExisting && chapterSource === "paste"
        ? "Saving chapter..."
        : "Uploading..."
      : "Starting processing..."
    : needsUsername
      ? "Set username to continue"
      : isManagingExisting
        ? replaceExisting
          ? "Update Chapter & Process"
          : "Add Chapter & Process"
        : startEmpty
          ? "Start empty project"
          : importPreview && !dismissPreview
            ? "Review structure above to continue"
            : "Upload manuscript"
  const shellClassName = `flex ${isInline ? "min-h-0" : "max-h-[92vh]"} w-full ${postImportReview || isManagingExisting ? "max-w-5xl" : "max-w-4xl"} flex-col overflow-hidden rounded-lg border transition-colors ${
    isDark
      ? isInline
        ? "border-white/10 bg-[#0B0B0B] text-slate-100"
        : "border-white/10 bg-[#0B0B0B] text-slate-100"
      : "border-black/5 bg-white text-slate-950"
  }`


  return {
    wizard, onClose, isInline, shellClassName, isManagingExisting, startEmpty, storyUnitLabel, storyUnitLabelTitle, isDark,
    uploadStage, processingBook, processingSummary, processingRetrying, retryProcessing, submit,
    inputRef, coverInputRef, newUploadAccept, files, setFiles, handleFilesSelected, handleCoverSelected,
    chapterUploadAccept: isScreenplayWorkspace ? SCREENPLAY_UPLOAD_ACCEPT : MANUSCRIPT_IMPORT_ACCEPT, primaryFile, isScreenplayWorkspace,
    importPreview, setImportPreview, dismissPreview, setDismissPreview, previewLoading, fetchPreview,
    setImportAsSingle, showEditor, setShowEditor, canUploadAuthorMode, needsUsername, settingUsername,
    usernameError, handleSetUsername, existingAuthorBooks, selectedExistingBook, existingBookSelectLabel,
    existingBookMenuRef, suggestedTags, series, uploadLimitCopy, addTag, removeTag, toggleSeries,
    chapterSource, setChapterSource, setError, chapterNumber, setChapterNumber, setChapterNumberDirty,
    replaceExisting, setReplaceExisting, chapterTitle, setChapterTitle, chapterText, setChapterText,
    chapterUploadHelp, splitIntoChapters, setSplitIntoChapters, chunkLongDocuments, setChunkLongDocuments,
    infoButtonClass, chapterReports, advancedSettingsOpen, setAdvancedSettingsOpen, preserveChapterNumbers,
    setPreserveChapterNumbers, preserveSourceChapters, setPreserveSourceChapters, coverFile, setCoverFile,
    autoExtractCover, setAutoExtractCover, error, uploading, uploadProgress, postImportReview, reportReady,
    postImportSynopsis, postImportPassages, postImportThreads, postImportSuggestions, user, confirm,
    booksApi, existingBookId, refetchBooks, primaryActionDisabled, primaryActionLabel,
  }
}
