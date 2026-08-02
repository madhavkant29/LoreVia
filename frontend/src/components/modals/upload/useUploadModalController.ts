"use client"

import axios from "axios"
import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import type React from "react"

import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { authApi } from "@/lib/api/auth"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { capture, captureTiming } from "@/lib/analytics/posthog"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { GENRE_TAGS } from "@/lib/constants/genreTags"
import { asQueryKey, bookCacheKey, booksListCacheKey, booksSeriesCacheKey, booksStatsCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { useBookModeStore } from "@/lib/stores/bookModeStore"
import type { BookMode } from "@/lib/stores/bookModeStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { normalizeProcessingStatus } from "@/lib/utils/processingStatus"
import type { Book, ChapterConsistencyReport, PaginatedSeries, UserStats } from "@/types/book"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"
import { useUploadWizardState } from "./useUploadWizardState"
import { useUploadWorkflow } from "./useUploadWorkflow"
import { normalizeTag, tagSimilarity } from "./uploadUtils"

const MAX_TAGS = 8
const TAG_SUGGESTION_LIMIT = 18

function getApiErrorDetail(error: unknown) {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  return typeof detail === "string" ? detail : null
}

type Options = {
  onClose: () => void
  initialMode: BookMode
  initialExistingBookId: string
  presentation: "modal" | "inline"
}

export function useUploadModalController({ onClose, initialMode, initialExistingBookId, presentation }: Options) {
  const wizard = useUploadWizardState(initialMode, initialExistingBookId)
  const {
    title, setTitle,
    author, setAuthor,
    authorManuallyEdited, setAuthorManuallyEdited,
    mode, setMode,
    startEmpty, setStartEmpty,
    selectedTags, setSelectedTags,
    customTag, setCustomTag,
    selectedSeriesIds, setSelectedSeriesIds,
    existingBookId, setExistingBookId,
    existingBookMenuOpen, setExistingBookMenuOpen,
    hoveredExistingBookId, setHoveredExistingBookId,
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
    workTypeDirty, setWorkTypeDirty,
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
  } = useQuery<Book[]>({
    queryKey: asQueryKey(booksListCacheKey(true)),
    queryFn: () => booksApi.list(true),
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
  const visibility: "private" = "private"
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
  const existingBookOptionStyle = (selected: boolean, hovered: boolean) => ({
    backgroundColor: selected ? "#2563eb" : hovered ? "#f3f4f6" : "#ffffff",
    color: selected ? "#ffffff" : "#000000",
  })

  useEffect(() => {
    setMode(initialMode)
  }, [initialMode])

  useEffect(() => {
    if (!canUploadAuthorMode && mode === "author") {
      setMode("reader")
    }
  }, [canUploadAuthorMode, mode])

  useEffect(() => {
    setExistingBookId(initialExistingBookId)
  }, [initialExistingBookId])

  useEffect(() => {
    setChapterNumberDirty(false)
  }, [initialExistingBookId])

  useEffect(() => {
    resetImportFeedback()
  }, [chapterSource, existingBookId, resetImportFeedback])

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
  }, [files, workTypeDirty])

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
      const target = `/${processingBook.id}?activation=1`
      const timer = setTimeout(() => {
        onClose()
        window.location.assign(target)
      }, 600)
      return () => clearTimeout(timer)
    }
    capture("processing_failed", { book_id: processingBook.id, mode: processingBook.mode })
  }, [onClose, processingBook, processingBookId])

  // Default new author-mode uploads to the current public username.
  useEffect(() => {
    if (mode === "author" && !isManagingExisting && !authorManuallyEdited && !author) {
      const preferred = user?.username
      if (preferred) setAuthor(preferred)
    }
  }, [author, authorManuallyEdited, isManagingExisting, mode, user?.username])

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

  const addCustomTag = () => {
    addTag(customTag)
    setCustomTag("")
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
  }, [chapterNumberDirty, isManagingExisting, replaceExisting, selectedExistingBook])

  useEffect(() => {
    if (!isManagingExisting || !selectedExistingBook) return
    setWorkType(selectedExistingBook.work_type)
  }, [isManagingExisting, selectedExistingBook])

  useEffect(() => {
    if (!existingBookMenuOpen) return
    const handlePointerDown = (event: MouseEvent) => {
      if (!existingBookMenuRef.current?.contains(event.target as Node)) {
        setExistingBookMenuOpen(false)
      }
    }
    document.addEventListener("mousedown", handlePointerDown)
    return () => document.removeEventListener("mousedown", handlePointerDown)
  }, [existingBookMenuOpen])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (isManagingExisting && !canSubmitExistingImport) {
      setError(chapterSource === "paste" ? "Paste a chapter before processing it." : "Please select a chapter file.")
      return
    }
    if (!isManagingExisting && !startEmpty && files.length === 0) {
      setError("Please select at least one file")
      return
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
        const response = await booksApi.importManuscript(existingBookId, {
          text: chapterSource === "paste" ? chapterText.trim() : undefined,
          title: chapterSource === "paste" ? chapterTitle.trim() || undefined : undefined,
          chapterNumber: chapterNumber ? parseInt(chapterNumber) : undefined,
          replaceExisting,
          splitIntoChapters,
          chunkLongDocuments,
          workType: effectiveWorkType,
          files: chapterSource === "upload" ? files : undefined,
        })
        bookId = response.book_id
        captureTiming("upload_first_result_ms", uploadStartedAtRef.current ?? 0, { mode: "author", kind: "manuscript_import" })
        setBookMode(response.book_id, "author")
        capture("book_uploaded", {
          mode: "author",
          kind: chapterSource === "paste" ? "single_chapter_paste" : "manuscript_import",
          work_type: effectiveWorkType,
          file_count: chapterSource === "upload" ? files.length : 0,
          chapter_source: chapterSource,
          replace_existing: replaceExisting,
          split_into_chapters: splitIntoChapters,
          chunk_long_documents: chunkLongDocuments,
        })
        setChapterReports(response.chapter_reports ?? [])
        const importedChapter = response.imported_chapters[0]
        if (importedChapter) {
          try {
            if (chapterSource === "paste" && chapterText.trim()) {
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
        // When importAsSingle is true, disable chapter splitting
        const effectiveSplit = importAsSingle ? false : true
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
      setUploadStage("processing")
      setUploadProgress(100)
      startedProcessing = true
      if (bookId) {
        setProcessingBookId(bookId)
      } else {
        onClose()
      }
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
  const newUploadAccept = isScreenplayWorkspace ? ".pdf,.txt,.md" : ".pdf,.epub,.docx,.txt,.md"
  const primaryFile = files[0] ?? null
  const primaryFileIsPdf = Boolean(primaryFile?.name?.toLowerCase().endsWith(".pdf"))
  const willUseBlankCoverFallback = !coverFile && (!primaryFileIsPdf || !autoExtractCover)
  const chapterUploadHelp = isScreenplayWorkspace
    ? "Upload a screenplay PDF, Fountain, TXT, or Markdown script segment. LoreVia will turn scenes into synthetic chapters for the rest of the pipeline."
    : "Click to select a chapter file. Use PDF, EPUB, DOCX, TXT, or Markdown."
  const processingSummary = processingBook?.processing
    ? normalizeProcessingStatus(processingBook.processing, processingBook)
    : null
  async function retryProcessing() {
    if (!processingBookId) return
    setProcessingRetrying(true)
    try {
      if (processingSummary?.resumeAvailable) {
        await booksApi.continueProcessing(processingBookId)
      } else {
        await booksApi.retryProcessing(processingBookId)
      }
      await refetchBooks()
    } finally {
      setProcessingRetrying(false)
    }
  }
  const uploadLimitCopy = uploadStats
    ? `${(uploadStats.private.active_analyzed_words ?? 0).toLocaleString()}/${(uploadStats.private.active_word_limit ?? 0).toLocaleString()} active words Â· ${(uploadStats.private.monthly_processed_words ?? 0).toLocaleString()}/${(uploadStats.private.monthly_processed_word_limit ?? 0).toLocaleString()} processed this month Â· ${((uploadStats.private.source_storage_bytes ?? 0) / 1024 ** 3).toFixed(1)}/${((uploadStats.private.source_storage_limit_bytes ?? 0) / 1024 ** 3).toFixed(0)} GB source storage${uploadStats.private.allowances_enforced ? "" : " (reporting only)"}.`
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
    inputRef, coverInputRef, newUploadAccept, files, setFiles, primaryFile, isScreenplayWorkspace,
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
