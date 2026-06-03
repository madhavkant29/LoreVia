"use client"
import axios from "axios"
import { useQuery } from "@tanstack/react-query"
import { memo, useEffect, useRef, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { authApi } from "@/lib/api/auth"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { useAuthStore } from "@/lib/stores/authStore"
import { useBookModeStore, type BookMode } from "@/lib/stores/bookModeStore"
import { GENRE_TAGS } from "@/lib/constants/genreTags"
import { asQueryKey, bookCacheKey, booksListCacheKey, booksSeriesCacheKey, booksStatsCacheKey } from "@/lib/query/cacheKeys"
import { capture } from "@/lib/analytics/posthog"
import type { Book, BookSeries, BookWorkType, ChapterConsistencyReport, ImportPreview, PaginatedSeries, SectionMeta, UserStats } from "@/types/book"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"
import { ImportStructureEditor } from "@/components/modals/ImportStructureEditor"

const MAX_TAGS = 8
const TAG_SUGGESTION_LIMIT = 18

function getApiErrorDetail(error: unknown) {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  return typeof detail === "string" ? detail : null
}

export const UploadModal = memo(function UploadModal({
  onClose,
  initialMode = "reader",
  initialExistingBookId = "",
  presentation = "modal",
}: {
  onClose: () => void
  initialMode?: BookMode
  initialExistingBookId?: string
  presentation?: "modal" | "inline"
}) {
  const [title, setTitle] = useState("")
  const [author, setAuthor] = useState("")
  const [authorManuallyEdited, setAuthorManuallyEdited] = useState(false)
  const [mode, setMode] = useState<BookMode>(initialMode)
  const [startEmpty, setStartEmpty] = useState(false)
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [customTag, setCustomTag] = useState("")
  const [selectedSeriesIds, setSelectedSeriesIds] = useState<string[]>([])
  const [existingBookId, setExistingBookId] = useState(initialExistingBookId)
  const [existingBookMenuOpen, setExistingBookMenuOpen] = useState(false)
  const [hoveredExistingBookId, setHoveredExistingBookId] = useState<string | null>(null)
  const [chapterSource, setChapterSource] = useState<"paste" | "upload">("paste")
  const [chapterNumber, setChapterNumber] = useState("")
  const [chapterNumberDirty, setChapterNumberDirty] = useState(false)
  const [chapterTitle, setChapterTitle] = useState("")
  const [chapterText, setChapterText] = useState("")
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [splitIntoChapters, setSplitIntoChapters] = useState(true)
  const [chunkLongDocuments, setChunkLongDocuments] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [workType, setWorkType] = useState<BookWorkType>("novel")
  const [workTypeDirty, setWorkTypeDirty] = useState(false)
  const [autoExtractCover, setAutoExtractCover] = useState(true)
  const [preserveChapterNumbers, setPreserveChapterNumbers] = useState(false)
  const [preserveSourceChapters, setPreserveSourceChapters] = useState(false)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [advancedSettingsOpen, setAdvancedSettingsOpen] = useState(true)
  const [usernameInput, setUsernameInput] = useState("")
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [settingUsername, setSettingUsername] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStage, setUploadStage] = useState<"idle" | "uploading" | "processing">("idle")
  const [processingBookId, setProcessingBookId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [postImportReview, setPostImportReview] = useState<EditorialReview | null>(null)
  const [postImportPassages, setPostImportPassages] = useState<EditorialReviewPassage[]>([])
  const [postImportSuggestions, setPostImportSuggestions] = useState<AdvisorSuggestion[]>([])
  const [postImportThreads, setPostImportThreads] = useState<PlotThread[]>([])
  const [postImportSynopsis, setPostImportSynopsis] = useState<ManuscriptSynopsis | null>(null)
  const [chapterReports, setChapterReports] = useState<ChapterConsistencyReport[]>([])
  const [reportReady, setReportReady] = useState<{ bookId: string; chapterNum?: number; text: string } | null>(null)
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [dismissPreview, setDismissPreview] = useState(false)
  const [importAsSingle, setImportAsSingle] = useState(false)
  const [showEditor, setShowEditor] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const coverInputRef = useRef<HTMLInputElement>(null)
  const existingBookMenuRef = useRef<HTMLDivElement>(null)
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
  }, [existingBookId, chapterSource])

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
      const timer = setTimeout(() => onClose(), 600)
      return () => clearTimeout(timer)
    }
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

  const resetImportFeedback = () => {
    setError(null)
    setPostImportReview(null)
    setPostImportPassages([])
    setPostImportSuggestions([])
    setPostImportThreads([])
    setPostImportSynopsis(null)
    setChapterReports([])
    setReportReady(null)
  }

  const fetchPreview = async () => {
    if (files.length === 0) return
    setPreviewLoading(true)
    setError(null)
    try {
      const preview = await booksApi.previewUpload(files[0], workType)
      setImportPreview(preview)
      setDismissPreview(false)
    } catch (e) {
      setError(getApiErrorDetail(e) || "Failed to analyze manuscript structure.")
    } finally {
      setPreviewLoading(false)
    }
  }

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
      setError(getApiErrorDetail(error) ?? "Upload failed. Please try again.")
      setProcessingBookId(null)
    } finally {
      setUploading(false)
      if (!startedProcessing) {
        setUploadStage("idle")
      }
    }
  }

  const loadPostImportReview = async (bookId: string, chapterNum: number | undefined, content: string) => {
    if (!content.trim()) {
      setError("Chapter imported, but there was no text available to review inline.")
      return
    }
    const [editorial, suggestions, threads, synopsis] = await Promise.all([
      intelligenceApi.editorialReview(bookId, content, chapterNum),
      intelligenceApi.advisorSuggestions(bookId),
      readerApi.getPlotThreads(bookId, chapterNum ?? 9999),
      intelligenceApi.synopsis(bookId, "minimal").catch(() => null),
    ])
    setPostImportReview(editorial.review)
    setPostImportPassages(editorial.retrieved_passages)
    setPostImportSuggestions(suggestions.suggestions.filter((item) => item.chapter_ref === null || item.chapter_ref <= (chapterNum ?? Number.MAX_SAFE_INTEGER)).slice(0, 5))
    setPostImportThreads(threads.filter((thread) => thread.status !== "resolved").slice(0, 6))
    setPostImportSynopsis(synopsis)
    setReportReady({ bookId, chapterNum, text: content })
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
    ? [
        processingBook.processing.stage ?? processingBook.processing.status,
        typeof processingBook.processing.progress_pct === "number" ? `${Math.round(processingBook.processing.progress_pct)}%` : null,
        typeof processingBook.processing.eta_seconds === "number"
          ? processingBook.processing.eta_seconds <= 0
            ? "almost done"
            : `${Math.max(1, Math.round(processingBook.processing.eta_seconds / 60))} min left`
          : null,
      ]
        .filter(Boolean)
        .join(" - ")
    : null
  const uploadLimitCopy = uploadStats
    ? uploadStats.private.upload_limit_unlimited
      ? "Uploads are still tracked here, and worldbuilding manuscripts count as uploads on every tier. Architect stays unlimited, even when worldbuilding is linked across a series."
      : typeof uploadStats.private.upload_limit === "number"
        ? `${uploadStats.private.total_uploads}/${uploadStats.private.upload_limit} uploads used. ${uploadStats.private.uploads_remaining ?? 0} remaining. Worldbuilding manuscripts count as uploads on every tier.`
        : null
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

  const content = (
      <div className={shellClassName} onClick={(e) => e.stopPropagation()}>
        <div className={`relative border-b px-6 py-5 ${isDark ? "border-white/10" : "border-slate-200/80"}`}>
          <div>
            <h2 className="text-xl font-semibold tracking-tight">{isManagingExisting ? `Add New ${storyUnitLabelTitle}` : "Upload book"}</h2>
            <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              {isManagingExisting
                ? "Paste or upload one scene, chapter, or script segment, process it incrementally, and review what changed before moving on."
                : "Bring in one manuscript, choose how it should be processed, and keep setup lightweight."}
            </p>
          </div>
          {!isManagingExisting ? (
            <div className={`hidden rounded-full px-3 py-1 text-xs font-medium md:inline-flex ${isDark ? "bg-white/5 text-slate-300" : "bg-slate-100 text-slate-600"}`}>
              Private workspace
            </div>
          ) : null}
          <button
            onClick={onClose}
            className={`absolute right-6 top-5 rounded-full p-2 text-xl leading-none transition-colors ${
              isDark ? "text-slate-400 hover:bg-white/5 hover:text-white" : "text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            }`}
            aria-label="Close upload modal"
          >
            x
          </button>
        </div>

        {uploadStage === "processing" && processingBook ? (
          <div className={`mb-4 rounded-xl border p-4 ${isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-amber-200" : "text-amber-700"}`}>Processing status</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-200" : "text-slate-700"}`}>
                  {processingSummary ?? "Your upload is still being processed."}
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className={`rounded-lg px-3 py-2 text-xs font-semibold transition ${
                  isDark ? "bg-white/10 text-slate-100 hover:bg-white/15" : "bg-white text-stone-800 hover:bg-stone-100"
                }`}
              >
                Close
              </button>
            </div>
          </div>
        ) : null}

        <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
          <div className="reader-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="flex flex-col gap-4">
          {!isManagingExisting && !startEmpty ? (
            <div className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-slate-50/80"}`}>
              <div className="mb-3">
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>File upload</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Upload one manuscript file to start your import.
                </p>
              </div>
              <div
                onClick={() => inputRef.current?.click()}
                className={`cursor-pointer rounded-lg border-2 border-dashed p-6 transition-colors ${
                  isDark
                    ? files.length > 0
                      ? "border-indigo-400/50 bg-indigo-500/10"
                      : "border-white/15 bg-black/20 hover:border-indigo-400"
                    : files.length > 0
                      ? "border-indigo-300 bg-indigo-50"
                      : "border-slate-300 bg-white hover:border-indigo-400"
                }`}
              >
                <input
                  ref={inputRef}
                  type="file"
                  multiple={false}
                  accept={newUploadAccept}
                  className="hidden"
                  onChange={e => setFiles(Array.from(e.target.files ?? []))}
                />
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className={`text-base font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>
                      {files.length > 0 ? primaryFile?.name : "Drop a manuscript here or click to browse"}
                    </p>
                    <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                      {files.length > 0
                        ? "Replace the selected file at any time before uploading."
                        : `Supported formats: ${isScreenplayWorkspace ? "PDF, TXT, Markdown" : "DOCX, PDF, EPUB, TXT, Markdown"}.`}
                    </p>
                  </div>
                  <div className={`inline-flex rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white text-slate-950" : "bg-slate-900 text-white"}`}>
                    {files.length > 0 ? "Replace file" : "Choose file"}
                  </div>
                </div>
              </div>

              {files.length > 0 && !importPreview && !dismissPreview ? (
                <div className="mt-4 flex items-center gap-3">
                  <button
                    type="button"
                    disabled={previewLoading}
                    onClick={fetchPreview}
                    className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                      isDark
                        ? "bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                        : "bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                    }`}
                  >
                    {previewLoading ? (
                      <span className="flex items-center gap-2">
                        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Analyzing structure...
                      </span>
                    ) : (
                      "Preview structure"
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => setDismissPreview(true)}
                    className={`text-sm ${isDark ? "text-slate-400 hover:text-slate-300" : "text-slate-500 hover:text-slate-700"}`}
                  >
                    Skip preview
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          {importPreview && !dismissPreview ? (
            <div className={`rounded-lg border p-5 ${isDark ? "border-indigo-500/30 bg-indigo-500/5" : "border-indigo-200 bg-indigo-50/80"}`}>
              <div className="mb-3 flex items-center justify-between">
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-indigo-300" : "text-indigo-600"}`}>
                  Structure preview
                </p>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  importPreview.confidence >= 0.8 ? (isDark ? "bg-green-500/20 text-green-300" : "bg-green-100 text-green-700") :
                  importPreview.confidence >= 0.5 ? (isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700") :
                  (isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700")
                }`}>
                  {Math.round(importPreview.confidence * 100)}% confident
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className={`rounded-lg p-3 ${isDark ? "bg-white/[0.06]" : "bg-white"}`}>
                  <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>Language</p>
                  <p className={`mt-1 text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>
                    {importPreview.detected_language.toUpperCase()}
                    {importPreview.language_confidence > 0 ? (
                      <span className="ml-1 text-xs font-normal opacity-60">{Math.round(importPreview.language_confidence * 100)}%</span>
                    ) : null}
                  </p>
                </div>
                <div className={`rounded-lg p-3 ${isDark ? "bg-white/[0.06]" : "bg-white"}`}>
                  <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>Chapters</p>
                  <p className={`mt-1 text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>
                    {importPreview.chapter_count}
                  </p>
                </div>
                <div className={`rounded-lg p-3 ${isDark ? "bg-white/[0.06]" : "bg-white"}`}>
                  <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>Front matter</p>
                  <p className={`mt-1 text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>
                    {importPreview.front_matter_count}
                  </p>
                </div>
                <div className={`rounded-lg p-3 ${isDark ? "bg-white/[0.06]" : "bg-white"}`}>
                  <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>TOC</p>
                  <p className={`mt-1 text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-900"}`}>
                    {importPreview.toc_detected ? "Detected" : "None"}
                  </p>
                </div>
              </div>

              {importPreview.sections.length > 0 ? (
                <div className="mt-3">
                  <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    Sections ({importPreview.sections.length})
                  </p>
                  <div className={`max-h-48 overflow-y-auto rounded-lg border ${isDark ? "border-white/10" : "border-slate-200"}`}>
                    {importPreview.sections.filter(s => s.type !== "unknown" || s.title).slice(0, 20).map((s) => (
                      <div key={s.id} className={`flex items-center gap-3 border-b px-3 py-2 text-xs last:border-b-0 ${isDark ? "border-white/5" : "border-slate-100"}`}>
                        <span className={`rounded px-1.5 py-0.5 font-medium ${
                          s.include_in_analysis
                            ? (isDark ? "bg-green-500/20 text-green-300" : "bg-green-100 text-green-700")
                            : (isDark ? "bg-slate-500/20 text-slate-400" : "bg-slate-100 text-slate-500")
                        }`}>
                          {s.type}
                        </span>
                        <span className={isDark ? "text-slate-300" : "text-slate-700"}>
                          {s.title || `Section ${s.number ?? "?"}`}
                        </span>
                        {!s.include_in_analysis ? (
                          <span className={`ml-auto text-[10px] ${isDark ? "text-slate-500" : "text-slate-400"}`}>excluded</span>
                        ) : null}
                      </div>
                    ))}
                    {importPreview.sections.length > 20 ? (
                      <div className={`px-3 py-2 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                        +{importPreview.sections.length - 20} more sections
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {importPreview.warnings.length > 0 ? (
                <div className="mt-3 space-y-1">
                  {importPreview.warnings.map((w, i) => (
                    <div key={i} className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs ${
                      w.severity === "error" ? (isDark ? "bg-red-500/10 text-red-300" : "bg-red-50 text-red-700") :
                      w.severity === "warning" ? (isDark ? "bg-amber-500/10 text-amber-300" : "bg-amber-50 text-amber-700") :
                      (isDark ? "bg-blue-500/10 text-blue-300" : "bg-blue-50 text-blue-700")
                    }`}>
                      <span className="mt-0.5 shrink-0">{w.severity === "error" ? "\u26A0" : w.severity === "warning" ? "\u25B2" : "\u2139"}</span>
                      <span>{w.message}</span>
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button
                  type="submit"
                  onClick={() => { setImportAsSingle(false) }}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                    isDark
                      ? "bg-indigo-600 text-white hover:bg-indigo-700"
                      : "bg-indigo-600 text-white hover:bg-indigo-700"
                  }`}
                >
                  Confirm &amp; Import
                </button>
                <button
                  type="submit"
                  onClick={() => { setImportAsSingle(true) }}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                    isDark
                      ? "border border-white/20 bg-white/5 text-slate-200 hover:bg-white/10"
                      : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  Import as single file
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowEditor(true)
                  }}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                    isDark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  Edit structure
                </button>
              </div>
            </div>
          ) : null}

          {importPreview && showEditor ? (
            <ImportStructureEditor
              sections={importPreview.sections}
              isDark={isDark}
              onSave={(updatedSections) => {
                setImportPreview({ ...importPreview, sections: updatedSections })
                setShowEditor(false)
              }}
              onCancel={() => setShowEditor(false)}
            />
          ) : null}

          {!isManagingExisting ? (
            <div className="mb-1">
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Optional metadata</p>
            </div>
          ) : null}

          {!isManagingExisting ? (
            <div className="grid gap-4 xl:grid-cols-2">
              <input
                type="text"
                placeholder="Title"
                value={title}
                onChange={e => setTitle(e.target.value)}
                onInput={e => setTitle((e.target as HTMLInputElement).value)}
                required
                className={`rounded-xl border px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                  isDark
                    ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500"
                    : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400"
                }`}
              />
              <div className="space-y-2">
              <input
                type="text"
                placeholder={mode === "author"
                  ? "Manuscript author or pen name"
                  : willUseBlankCoverFallback
                    ? "Author (shown on blank cover if no cover is found)"
                    : "Author (optional)"}
                value={author}
                onChange={(e) => {
                  setAuthor(e.target.value)
                  setAuthorManuallyEdited(true)
                }}
                onInput={(e) => {
                  setAuthor((e.target as HTMLInputElement).value)
                  setAuthorManuallyEdited(true)
                }}
                className={`w-full rounded-xl border px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                  isDark
                    ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500"
                    : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400"
                }`}
              />
              {willUseBlankCoverFallback ? (
                <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  If LoreVia cannot find a cover, it will generate a blank cover page using the title and author.
                </p>
              ) : null}
              {mode === "author" ? (
                <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  This name appears on this manuscript only. It defaults to your username, but you can change it here if this book should use a different pen name or byline.
                </p>
              ) : null}
            </div>
            </div>
          ) : null}

          <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Manuscript type</p>
                {isManagingExisting ? (
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    {selectedExistingBook
                      ? `This workspace is set to ${selectedExistingBook.work_type}.`
                      : "Choose how LoreVia should interpret this manuscript."}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {([
                { value: "novel", label: "Novel" },
                { value: "screenplay", label: "Screenplay" },
              ] as const).map((option) => {
                const active = effectiveWorkType === option.value
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      if (isManagingExisting && selectedExistingBook) return
                      setWorkType(option.value)
                      setWorkTypeDirty(true)
                    }}
                    disabled={isManagingExisting && !!selectedExistingBook}
                    className={`rounded-xl border px-4 py-3 text-left transition disabled:cursor-not-allowed disabled:opacity-80 ${
                      active
                        ? isDark
                          ? "border-indigo-400/50 bg-indigo-400/15 text-slate-100"
                          : "border-indigo-300 bg-indigo-50 text-stone-900"
                        : isDark
                          ? "border-white/10 bg-black/20 text-slate-300 hover:bg-white/5"
                          : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                    }`}
                  >
                    <p className="text-sm font-semibold">{option.label}</p>
                  </button>
                )
              })}
            </div>
          </div>

          <div className={`rounded-xl border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Workspace mode</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  {mode === "reader"
                    ? "Spoiler-aware workspace aligned to reading progress."
                    : "Full analysis with exports and writing-focused tools."}
                </p>
              </div>
            </div>
            <div className={`mt-3 inline-flex w-full rounded-full p-1 ${isDark ? "border border-white/10 bg-white/5" : "border border-stone-200 bg-stone-100"}`}>
              {(["reader", "author"] as const).map((value) => {
                const active = mode === value
                const locked = value === "author" && !canUploadAuthorMode
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => {
                      if (locked) return
                      setMode(value)
                    }}
                    disabled={locked}
                    className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
                      active
                        ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950"
                        : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white/70"
                    }`}
                  >
                    {value === "reader" ? "Reading mode" : locked ? "Author mode locked" : "Author mode"}
                  </button>
                )
              })}
            </div>
            {!canUploadAuthorMode ? (
              <p className={`mt-3 text-xs leading-5 ${isDark ? "text-amber-200" : "text-amber-700"}`}>
                Author uploads require Author or Architect access. Collaboration-only access stays read-only.
              </p>
            ) : null}
            {uploadLimitCopy ? (
              <p className={`mt-3 text-xs leading-5 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                {uploadLimitCopy}
              </p>
            ) : null}
            {!isManagingExisting && mode === "author" && canUploadAuthorMode ? (
              <div className={`mt-4 inline-flex w-full rounded-full p-1 ${isDark ? "border border-white/10 bg-white/5" : "border border-stone-200 bg-stone-100"}`}>
                <button
                  type="button"
                  onClick={() => {
                    setStartEmpty(false)
                    setFiles([])
                  }}
                  className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${
                    !startEmpty
                      ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950"
                      : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white/70"
                  }`}
                >
                  Upload manuscript
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStartEmpty(true)
                    setFiles([])
                  }}
                  className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${
                    startEmpty
                      ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950"
                      : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white/70"
                  }`}
                >
                  Start empty project
                </button>
              </div>
            ) : null}
            {mode === "author" && !user?.username ? (
              <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-amber-500/30 bg-amber-500/10" : "border-amber-300 bg-amber-50"}`}>
                <p className={`text-sm font-medium mb-2 ${isDark ? "text-amber-200" : "text-amber-800"}`}>Select a username to use Author mode</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="username"
                    value={usernameInput}
                    onChange={(e) => setUsernameInput(e.target.value)}
                    className={`flex-1 rounded-lg border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-gray-300 bg-white text-slate-950"}`}
                    minLength={3}
                    maxLength={32}
                  />
                  <button
                    type="button"
                    onClick={handleSetUsername}
                    disabled={settingUsername || usernameInput.length < 3}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {settingUsername ? "Saving..." : "Set"}
                  </button>
                </div>
                {usernameError && <p className="mt-2 text-xs text-red-400">{usernameError}</p>}
                <p className={`mt-2 text-xs ${isDark ? "text-amber-300/70" : "text-amber-600"}`}>
                  Select the username you want to appear publicly on LoreVia. New author uploads default to this username, but each manuscript can still use a different author or pen name.
                </p>
              </div>
            ) : null}
            {mode === "author" && existingAuthorBooks.length > 0 ? (
              <div className="mt-4">
                <label className={`mb-2 block text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Manage existing author upload
                </label>
                <div className="relative" ref={existingBookMenuRef}>
                  <button
                    type="button"
                    aria-haspopup="listbox"
                    aria-expanded={existingBookMenuOpen}
                    onClick={() => setExistingBookMenuOpen((open) => !open)}
                    className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left text-sm ${isDark ? "border-white/10" : "border-gray-300"}`}
                    style={{ backgroundColor: "#ffffff", color: "#000000" }}
                  >
                    <span className="truncate">{existingBookSelectLabel}</span>
                    <span aria-hidden="true" className="ml-3 text-base leading-none">v</span>
                  </button>
                  {existingBookMenuOpen ? (
                    <div
                      role="listbox"
                      className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-gray-300 bg-white py-1"
                    >
                      <button
                        type="button"
                        role="option"
                        aria-selected={existingBookId === ""}
                        onClick={() => {
                          setExistingBookId("")
                          setChapterNumberDirty(false)
                          setExistingBookMenuOpen(false)
                        }}
                        onMouseEnter={() => setHoveredExistingBookId("")}
                        onMouseLeave={() => setHoveredExistingBookId((current) => (current === "" ? null : current))}
                        className="block w-full px-3 py-2 text-left text-sm"
                        style={existingBookOptionStyle(existingBookId === "", hoveredExistingBookId === "")}
                      >
                        Create a new upload
                      </button>
                      {existingAuthorBooks.map((book) => (
                        <button
                          key={book.id}
                          type="button"
                          role="option"
                          aria-selected={existingBookId === book.id}
                          onClick={() => {
                            setExistingBookId(book.id)
                            setChapterNumberDirty(false)
                            setExistingBookMenuOpen(false)
                          }}
                          onMouseEnter={() => setHoveredExistingBookId(book.id)}
                          onMouseLeave={() => setHoveredExistingBookId((current) => (current === book.id ? null : current))}
                          className="block w-full px-3 py-2 text-left text-sm"
                          style={existingBookOptionStyle(existingBookId === book.id, hoveredExistingBookId === book.id)}
                        >
                          {book.title}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Genres and moods</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Optional tags help organize tone, genre, and mood.</p>
              </div>
              <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{selectedTags.length}/{MAX_TAGS}</span>
            </div>
          <div className={`group relative rounded-xl border p-1 transition-all ${
            isDark ? "border-white/10 bg-white/5 focus-within:border-indigo-500/50" : "border-gray-300 bg-white"
          }`}>
            <div className="flex items-center gap-2 px-2 py-1">
              <input
                type="text"
                value={customTag}
                onChange={e => setCustomTag(e.target.value)}
                placeholder="Add genres or moods..."
                className="flex-1 bg-transparent py-1.5 text-sm outline-none placeholder:text-slate-500"
              />
              {customTag.trim().length > 0 && (
                <button
                  type="button"
                  onClick={addCustomTag}
                  className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-indigo-700"
                >
                  Add
                </button>
              )}
            </div>

            {/* Suggestions dropdown - Triggers at 2 characters */}
            {shouldShowTagSuggestions && suggestedTags.length > 0 && (
              <div className={`mt-1 border-t ${isDark ? "border-white/10" : "border-gray-100"}`}>
                <div className="px-3 pt-3">
                  <p className={`text-3xs font-bold uppercase tracking-wider ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                    Suggestions
                  </p>
                </div>
                <div className="max-h-40 overflow-y-auto px-2 pb-2 pt-2">
                  {suggestedTags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => {
                        addTag(tag)
                        setCustomTag("")
                      }}
                      className={`mb-1 flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-xs font-medium transition ${
                        isDark
                          ? "border-white/10 text-slate-200 hover:bg-white/10"
                          : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <span>{tag}</span>
                      <span className={isDark ? "text-slate-400" : "text-slate-400"}>Add</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          {selectedTags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {selectedTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => removeTag(tag)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                    isDark
                      ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/10"
                      : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  {tag} x
                </button>
              ))}
            </div>
          ) : null}
          </div>

          {series.length > 0 ? (
            <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Add to series</p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    Optional. Attach this upload to one or more existing series now.
                  </p>
                </div>
                <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                  {selectedSeriesIds.length} selected
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {series.map((seriesItem) => {
                  const selected = selectedSeriesIds.includes(seriesItem.id)
                  return (
                    <button
                      key={seriesItem.id}
                      type="button"
                      onClick={() => toggleSeries(seriesItem.id)}
                      className={`rounded-full border px-3 py-2 text-xs font-medium transition ${
                        selected
                          ? isDark
                            ? "border-indigo-400/40 bg-indigo-400/20 text-indigo-100"
                            : "border-indigo-300 bg-indigo-100 text-indigo-800"
                          : isDark
                            ? "border-white/10 text-slate-300 hover:bg-white/5"
                            : "border-slate-300 text-slate-700 hover:bg-white"
                      }`}
                    >
                      {seriesItem.name}
                    </button>
                  )
                })}
              </div>
            </div>
          ) : null}

          {isManagingExisting ? (
            <div className={`rounded-md border p-5 ${isDark ? "border-indigo-500/20 bg-white/[0.03]" : "border-indigo-200 bg-slate-50"}`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-indigo-700"}`}>Single-{isScreenplayWorkspace ? "script" : "chapter"} workflow</p>
                  <p className={`mt-2 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    LoreVia will attach this {isScreenplayWorkspace ? "scene batch or script segment" : "chapter"} to {selectedExistingBook ? `"${selectedExistingBook.title}"` : "your selected manuscript"}, update character memory and thread data, then surface continuity risks from the fresh ingest.
                  </p>
                </div>
                <div className={`rounded-md border px-4 py-3 text-xs ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-white bg-white text-stone-600"}`}>
                  <p className="font-semibold">After processing</p>
                  <p className="mt-1">You'll get a fresh summary, new-character changes, thread movement, and continuity review.</p>
                </div>
              </div>

              <div className={`mt-4 inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-white/5" : "border border-stone-200 bg-white/80"}`}>
                {([
                  { value: "paste", label: isScreenplayWorkspace ? "Paste script" : "Paste chapter" },
                  { value: "upload", label: "Upload file" },
                ] as const).map((option) => {
                  const active = chapterSource === option.value
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setChapterSource(option.value)
                        setError(null)
                      }}
                      className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                        active
                          ? isDark ? "bg-white text-slate-950" : "bg-indigo-600 text-white"
                          : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-stone-100"
                      }`}
                    >
                      {option.label}
                    </button>
                  )
                })}
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-[0.9fr_1.1fr]">
                <div className="space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      type="number"
                      min={1}
                      placeholder={`${storyUnitLabelTitle} number`}
                      value={chapterNumber}
                      onChange={(e) => {
                        setChapterNumber(e.target.value)
                        setChapterNumberDirty(true)
                      }}
                      className={`rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-gray-300 bg-white text-slate-950"}`}
                    />
                    <label className={`flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-gray-300 bg-white text-slate-700"}`}>
                      <input type="checkbox" checked={replaceExisting} onChange={(e) => setReplaceExisting(e.target.checked)} />
                      {`Replace ${storyUnitLabel}`}
                    </label>
                  </div>

                  {chapterSource === "paste" ? (
                    <>
                      <input
                        type="text"
                        placeholder={`${storyUnitLabelTitle} title (optional)`}
                        value={chapterTitle}
                        onChange={(e) => setChapterTitle(e.target.value)}
                        className={`rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500" : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400"}`}
                      />
                      <textarea
                        value={chapterText}
                        onChange={(e) => setChapterText(e.target.value)}
                        placeholder={isScreenplayWorkspace
                          ? "Paste screenplay text here. LoreVia will split scenes, refresh character profiles, and immediately run continuity checks."
                          : "Paste one chapter here. LoreVia will save it into the manuscript, refresh character profiles, and immediately run continuity checks."}
                        rows={14}
                        className={`min-h-[280px] rounded-xl border px-3 py-3 text-sm leading-6 outline-none transition ${isDark ? "border-white/10 bg-black/20 text-slate-100 placeholder:text-slate-500 focus:border-indigo-400/50" : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400 focus:border-indigo-400"}`}
                      />
                      <div className={`flex items-center justify-between text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        <span>{chapterText.trim() ? `${chapterText.trim().split(/\s+/).length} words ready` : `No ${storyUnitLabel} text pasted yet`}</span>
                        <span>{replaceExisting ? `Will replace the selected ${storyUnitLabel} number` : `Will append if the ${storyUnitLabel} number is new`}</span>
                      </div>
                    </>
                  ) : (
                    <div
                      onClick={() => inputRef.current?.click()}
                      className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
                        isDark
                          ? "border-white/15 bg-white/[0.03] hover:border-indigo-400"
                          : "border-gray-300 bg-white hover:border-indigo-400"
                      }`}
                    >
                      <input
                        ref={inputRef}
                        type="file"
                        multiple
                        accept={isScreenplayWorkspace ? ".pdf,.fountain,.txt,.md" : ".pdf,.epub,.docx,.txt,.md"}
                        className="hidden"
                        onChange={e => setFiles(Array.from(e.target.files ?? []))}
                      />
                      {files.length > 0 ? (
                        <p className={`text-sm ${isDark ? "text-slate-100" : "text-slate-700"}`}>
                          {files.length === 1 ? files[0].name : `${files.length} files selected`}
                        </p>
                      ) : (
                        <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-400"}`}>
                          {chapterUploadHelp}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <div className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-white bg-white"}`}>
                    <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Processing options</p>
                    <div className="mt-3 flex flex-wrap gap-3">
                      <label className={`flex items-center gap-2 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                        <input type="checkbox" checked={splitIntoChapters} onChange={(e) => setSplitIntoChapters(e.target.checked)} />
                        <span className="inline-flex items-center gap-1">
                          <span>{isScreenplayWorkspace ? "Split screenplay PDFs into scenes" : "Split PDFs into chapters"}</span>
                          <button
                            type="button"
                            title={isScreenplayWorkspace
                              ? "Keeps detected scene headings together. If screenplay formatting is noisy, LoreVia will still build a stable scene order."
                              : "Keeps detected chapters together. If chapter numbering is inconsistent, LoreVia will use its normal sequential split."}
                            aria-label={isScreenplayWorkspace ? "What Split screenplay PDFs into scenes means" : "What Split PDFs into chapters means"}
                            className={infoButtonClass}
                          >
                            i
                          </button>
                        </span>
                      </label>
                      <label className={`flex items-center gap-2 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                        <input type="checkbox" checked={chunkLongDocuments} onChange={(e) => setChunkLongDocuments(e.target.checked)} />
                        <span className="inline-flex items-center gap-1">
                          <span>Chunk long files</span>
                          <button
                            type="button"
                            title="Breaks long text into smaller pieces (3,500 words per chapter) for easier processing. This may create more chapters than your original manuscript."
                            aria-label="What Chunk long files means"
                            className={infoButtonClass}
                          >
                            i
                          </button>
                        </span>
                      </label>
                      {chunkLongDocuments ? (
                        <p className={`ml-5 mt-1 text-xs ${isDark ? "text-amber-300" : "text-amber-700"}`}>
                          Warning: This will split long chapters at 3,500 words. A 35,000-word manuscript may become 10+ chapters.
                        </p>
                      ) : null}
                    </div>
                    <div className={`mt-4 rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
                      <p className="font-semibold">What LoreVia updates</p>
                      <p className="mt-1">{`Character state, relationship extraction, plot-thread analysis, and ${storyUnitLabel}-level continuity flags are all rerun from this ${storyUnitLabel} ingest.`}</p>
                      {!replaceExisting && selectedExistingBook ? (
                        <p className="mt-2 text-xs opacity-80">
                          {`Suggested next ${storyUnitLabel}: ${(selectedExistingBook.total_chapters ?? 0) + 1}`}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  {chapterReports.length > 0 ? (
                    <div className={`rounded-xl border p-4 ${isDark ? "border-teal-500/20 bg-teal-500/10" : "border-teal-200 bg-teal-50"}`}>
                      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-teal-200" : "text-teal-800"}`}>Latest chapter outcome</p>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {buildImportOutcomeCards(chapterReports).map((item) => (
                          <div key={item.label} className={`rounded-lg border px-3 py-3 ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-white bg-white text-stone-800"}`}>
                            <p className="text-lg font-semibold">{item.value}</p>
                            <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{item.label}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}>
                      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Ready for incremental ingest</p>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                        {`Choose a ${storyUnitLabel} number, paste or upload a single ${storyUnitLabel}, and LoreVia will return a focused report instead of making you dig through the whole manuscript again.`}
                      </p>
                    </div>
                  )}

                  {chapterReports.some((report) => report.continuity_flags.length > 0) ? (
                    <div className={`rounded-xl border p-4 ${isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
                      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-amber-200" : "text-amber-800"}`}>{`Fresh ${storyUnitLabel} continuity flags`}</p>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                        {`These were surfaced directly from the ${storyUnitLabel} you just imported, after LoreVia refreshed stored character and story state.`}
                      </p>
                      <div className="mt-3 space-y-2">
                        {chapterReports.flatMap((report) =>
                          report.continuity_flags.map((flag, index) => (
                            <div key={`${report.chapter_number}-fresh-${index}`} className={`rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-white bg-white text-stone-700"}`}>
                              <p className="font-semibold">{storyUnitLabelTitle} {report.chapter_number}{report.chapter_title ? ` - ${report.chapter_title}` : ""}</p>
                              <p className="mt-1">{flag}</p>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          {!isManagingExisting ? (
          <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
            <button
              type="button"
              onClick={() => setAdvancedSettingsOpen((current) => !current)}
              className="flex w-full items-center justify-between text-left"
            >
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Advanced import settings</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Optional controls for structure, chapter preservation, and cover handling.
                </p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-slate-700"}`}>
                {advancedSettingsOpen ? "Hide" : "Show"}
              </span>
            </button>
            {advancedSettingsOpen ? (
            <div className="mt-4">
            <div className="mb-4">
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={preserveChapterNumbers || preserveSourceChapters}
                  onChange={(e) => setPreserveChapterNumbers(e.target.checked)}
                  disabled={preserveSourceChapters}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed"
                />
                <div>
                  <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-900"}`}>{isScreenplayWorkspace ? "Preserve detected scene order from the source file" : "Preserve chapter numbers from the source file"}</p>
                </div>
              </label>
            </div>

            <div className="mb-4">
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={preserveSourceChapters}
                  onChange={(e) => {
                    const nextChecked = e.target.checked
                    setPreserveSourceChapters(nextChecked)
                    if (nextChecked) {
                      setPreserveChapterNumbers(true)
                    }
                  }}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-900"}`}>
                    {isScreenplayWorkspace ? "Keep each detected scene exactly as uploaded" : "Keep each detected chapter exactly as uploaded"}
                  </p>
                </div>
              </label>
            </div>

            {/* Separate Cover Upload - Always visible */}
            <div className="mb-4">
              <input
                ref={coverInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null
                  setCoverFile(file)
                  if (file) {
                    setAutoExtractCover(false)
                  }
                }}
              />
              <button
                type="button"
                onClick={() => coverInputRef.current?.click()}
                className={`w-full rounded-lg border px-3 py-2.5 text-sm transition ${
                  isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-gray-300 bg-white text-slate-700 hover:bg-gray-50"
                }`}
              >
                {coverFile ? `Cover selected: ${coverFile.name}` : "Upload separate cover image"}
              </button>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                Select a separate cover image file (PNG, JPEG, WebP)
              </p>
            </div>

            {/* Auto-extract checkbox - disabled when cover file is uploaded */}
            <label className={`flex items-start gap-3 ${coverFile ? "opacity-50" : ""}`}>
              <input
                type="checkbox"
                checked={autoExtractCover}
                onChange={(e) => {
                  setAutoExtractCover(e.target.checked)
                  if (e.target.checked) {
                    setCoverFile(null)
                  }
                }}
                disabled={!!coverFile}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed"
              />
              <div>
                <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-900"}`}>Use the first PDF page as the book cover</p>
              </div>
            </label>
            </div>
            ) : null}
          </div>
          ) : null}

          {error && <p className="text-sm text-red-500">{error}</p>}

          {uploading ? (
            <div
              className={`rounded-xl border p-3 ${
                isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"
              }`}
            >
              <div className="mb-2 flex items-center justify-between text-xs font-medium">
                <span className={isDark ? "text-slate-300" : "text-slate-600"}>
                  {uploadStage === "uploading" ? "Uploading file" : "Handing off for processing"}
                </span>
                <span className={isDark ? "text-slate-200" : "text-slate-700"}>
                  {uploadStage === "uploading" ? `${uploadProgress}%` : "Queued"}
                </span>
              </div>
              <div className={`h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-gray-200"}`}>
                <div
                  className="h-full rounded-full bg-indigo-600 transition-all duration-200"
                  style={{ width: `${uploadStage === "processing" ? 100 : uploadProgress}%` }}
                />
              </div>
              <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                {uploadStage === "uploading"
                  ? "Large PDFs can take a bit depending on your network speed."
                  : isManagingExisting
                    ? "Your chapter is in LoreVia. Incremental extraction and continuity review are being refreshed now."
                    : "Your book upload finished. Parsing and AI extraction continue in the background."}
              </p>
            </div>
          ) : null}

          {chapterReports.length > 0 ? (
            <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-50"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>{`${storyUnitLabelTitle} consistency report`}</p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{`Generated from the latest import so you can review the ${storyUnitLabel} in under 30 seconds.`}</p>
                </div>
              </div>

              <div className="mt-4 space-y-4">
                {chapterReports.map((report) => (
                  <div key={`${report.chapter_number}-${report.chapter_title ?? "untitled"}`} className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-white bg-white"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                          {storyUnitLabelTitle} {report.chapter_number}{report.chapter_title ? ` - ${report.chapter_title}` : ""}
                        </p>
                        <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{report.summary}</p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 xl:grid-cols-2">
                      <div className="space-y-3">
                        <ReportList
                          title="New characters"
                          emptyLabel="No new characters detected."
                          items={report.new_characters.map((character) => {
                            const details = [character.role, character.arc_summary].filter(Boolean).join(" - ")
                            return details ? `${character.name} (${details})` : character.name
                          })}
                          isDark={isDark}
                        />
                        <ReportList
                          title="Relationship changes"
                          emptyLabel="No new relationship shifts were recorded."
                          items={report.relationship_changes}
                          isDark={isDark}
                        />
                      </div>

                      <div className="space-y-3">
                        <ReportList
                          title="Plot threads opened"
                          emptyLabel="No new plot threads opened in this chapter."
                          items={report.plot_threads_opened}
                          isDark={isDark}
                        />
                        <ReportList
                          title="Plot threads resolved"
                          emptyLabel="No plot threads resolved in this chapter."
                          items={report.plot_threads_resolved}
                          isDark={isDark}
                        />
                        <ReportList
                          title="Continuity flags"
                          emptyLabel="No immediate continuity flags were found."
                          items={report.continuity_flags}
                          isDark={isDark}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {postImportReview ? (
            <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-50"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Immediate continuity review</p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{postImportReview.overall_verdict}</p>
                </div>
                {reportReady ? (
                  <button
                    type="button"
                    onClick={async () => {
                      const blob = await intelligenceApi.continuityReport(reportReady.bookId, reportReady.text, "pdf", reportReady.chapterNum)
                      const url = URL.createObjectURL(blob)
                      const link = document.createElement("a")
                      link.href = url
                      link.download = "continuity-report.pdf"
                      link.click()
                      URL.revokeObjectURL(url)
                    }}
                    className={`rounded-full border px-4 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-100"}`}
                  >
                    Download continuity report
                  </button>
                ) : null}
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                <div className="space-y-3">
                  {postImportSynopsis ? (
                    <div>
                      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Spoiler-light synopsis</p>
                      <div className={`rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                        <p>{postImportSynopsis.synopsis}</p>
                        {postImportSynopsis.focus_points.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {postImportSynopsis.focus_points.map((point) => (
                              <span key={point} className={`rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-700"}`}>{point}</span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                  <div>
                    <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Broader editorial continuity review</p>
                    <p className={`mb-3 text-xs leading-5 ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                      These come from LoreVia&apos;s wider story-context review. Fresh chapter-specific flags appear above in the chapter report.
                    </p>
                    {postImportReview.continuity_issues.length > 0 ? postImportReview.continuity_issues.map((issue, index) => (
                      <div key={`${issue.title}-${index}`} className={`mb-2 rounded-lg border px-3 py-3 text-sm ${isDark ? "border-amber-500/20 bg-amber-500/10 text-slate-200" : "border-amber-200 bg-amber-50 text-stone-700"}`}>
                        <p className="font-semibold">{issue.title}</p>
                        <p className="mt-1 text-xs opacity-80">{issue.description}</p>
                        {issue.suggestion ? <p className="mt-2 text-xs font-medium opacity-90">{issue.suggestion}</p> : null}
                      </div>
                    )) : (
                      <p className={`text-sm ${isDark ? "text-teal-300" : "text-teal-700"}`}>No continuity issues found in this upload.</p>
                    )}
                  </div>

                  {postImportReview.insertion_opportunities.length > 0 ? (
                    <div>
                      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Best insertion opportunities</p>
                      <div className="space-y-2">
                        {postImportReview.insertion_opportunities.map((item, index) => (
                          <div key={`${item.title}-${index}`} className={`rounded-lg border px-3 py-3 text-sm ${isDark ? "border-teal-500/20 bg-teal-500/10 text-slate-200" : "border-teal-200 bg-teal-50 text-stone-700"}`}>
                            <p className="font-semibold">{item.title}</p>
                            <p className="mt-1 text-xs opacity-80">Chapter {item.target_chapter}{item.target_chapter_title ? ` - ${item.target_chapter_title}` : ""}</p>
                            <p className="mt-2 text-xs leading-5 opacity-80">{item.problem}</p>
                            <p className="mt-2 text-xs font-medium opacity-95">Add: {item.what_to_add}</p>
                            <p className="mt-2 text-xs opacity-80">{item.why_here}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {postImportPassages.length > 0 ? (
                    <div>
                      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Cross-referenced passages</p>
                      <div className="space-y-2">
                        {postImportPassages.map((passage, index) => (
                          <div key={`${passage.chapter_num}-${index}`} className={`rounded-lg border px-3 py-3 text-xs leading-5 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                            <p className={`mb-1 font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>Chapter {passage.chapter_num}{passage.chapter_title ? ` - ${passage.chapter_title}` : ""}</p>
                            <p>{passage.excerpt}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="space-y-3">
                  <div>
                    <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Forgotten threads</p>
                    {postImportThreads.length > 0 ? postImportThreads.map((thread) => (
                      <div key={thread.id} className={`mb-2 rounded-lg border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                        <p className="font-semibold">{thread.title}</p>
                        <p className="mt-1 text-xs opacity-80">Introduced in chapter {thread.introduced_at ?? "?"} - {thread.status}</p>
                      </div>
                    )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No unresolved thread warnings loaded.</p>}
                  </div>

                  <div>
                    <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Improvement prompts</p>
                    {postImportSuggestions.length > 0 ? postImportSuggestions.map((item) => (
                      <div key={item.id} className={`mb-2 rounded-lg border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                        <p className="font-semibold">{item.title}</p>
                        <p className="mt-1 text-xs opacity-80">{item.description}</p>
                      </div>
                    )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No follow-up prompts were generated.</p>}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          </div>
          </div>
          <div className={`sticky bottom-0 border-t px-6 py-4 ${isDark ? "border-white/10 bg-[#0B0B0B]" : "border-slate-200 bg-white"}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                {isManagingExisting
                  ? `LoreVia will process this ${storyUnitLabel} after upload.`
                  : importPreview && !dismissPreview
                    ? "Review the detected structure, then confirm to import."
                    : files.length > 0
                      ? "Ready to upload your manuscript."
                      : "Select a file to enable upload."}
              </p>
              <div className="flex items-center gap-3">
                {isManagingExisting ? (
                  <button
                    type="button"
                    onClick={async () => {
                      if (!confirm("Delete this project and all its data? This cannot be undone.")) return
                      try {
                        await booksApi.delete(existingBookId)
                        void refetchBooks()
                        onClose()
                      } catch {
                        setError("Failed to delete project.")
                      }
                    }}
                    className={`rounded-xl px-4 py-2.5 text-sm font-medium transition ${
                      isDark ? "border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20" : "border border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
                    }`}
                  >
                    Delete &amp; reimport
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={onClose}
                  className={`rounded-xl px-4 py-2.5 text-sm font-medium transition ${
                    isDark ? "border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={primaryActionDisabled}
                  className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {primaryActionLabel}
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>
  )

  return isInline ? content : (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 pt-6 md:pt-10"
      onClick={onClose}
    >
      {content}
    </div>
  )
})

function normalizeTag(rawTag: string): string {
  return rawTag
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
}

function normalizeKeywords(input: string) {
  return input
    .toLowerCase()
    .split(/[^a-z0-9]+/i)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2)
}

function tagSimilarity(tag: string, query: string) {
  const trimmed = query.trim()
  if (!trimmed) return 0

  const tagLower = tag.toLowerCase()
  const queryLower = trimmed.toLowerCase()
  if (tagLower.includes(queryLower) || queryLower.includes(tagLower)) return 1

  const aTokens = new Set(normalizeKeywords(tag))
  const bTokens = new Set(normalizeKeywords(trimmed))
  if (aTokens.size === 0 || bTokens.size === 0) return 0

  let intersection = 0
  for (const token of aTokens) {
    if (bTokens.has(token)) intersection += 1
  }
  const union = aTokens.size + bTokens.size - intersection
  return union === 0 ? 0 : intersection / union
}

function buildImportOutcomeCards(reports: ChapterConsistencyReport[]) {
  const totals = reports.reduce(
    (acc, report) => {
      acc.chapters += 1
      acc.characters += report.new_characters.length
      acc.relationships += report.relationship_changes.length
      acc.openThreads += report.plot_threads_opened.length
      acc.continuity += report.continuity_flags.length
      return acc
    },
    { chapters: 0, characters: 0, relationships: 0, openThreads: 0, continuity: 0 }
  )

  return [
    { label: "Chapters processed", value: String(totals.chapters) },
    { label: "New characters found", value: String(totals.characters) },
    { label: "Relationship shifts", value: String(totals.relationships) },
    { label: "Plot threads opened", value: String(totals.openThreads) },
    { label: "Continuity flags surfaced", value: String(totals.continuity) },
  ]
}

function ReportList({
  title,
  items,
  emptyLabel,
  isDark,
}: {
  title: string
  items: string[]
  emptyLabel: string
  isDark: boolean
}) {
  return (
    <div>
      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>{title}</p>
      {items.length > 0 ? (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={`${title}-${index}-${item}`} className={`rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
              {item}
            </div>
          ))}
        </div>
      ) : (
        <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{emptyLabel}</p>
      )}
    </div>
  )
}
