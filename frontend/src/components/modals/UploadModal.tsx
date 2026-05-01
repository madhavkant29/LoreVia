"use client"
import { useEffect, useRef, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { authApi } from "@/lib/api/auth"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { useAuthStore } from "@/lib/stores/authStore"
import { useBookModeStore, type BookMode } from "@/lib/stores/bookModeStore"
import { GENRE_TAGS } from "@/lib/constants/genreTags"
import { capture } from "@/lib/analytics/posthog"
import type { Book, BookSeries, ChapterConsistencyReport } from "@/types/book"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"

const MAX_TAGS = 8
const TAG_SUGGESTION_LIMIT = 18

export function UploadModal({
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
  const [mode, setMode] = useState<BookMode>(initialMode)
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [customTag, setCustomTag] = useState("")
  const [series, setSeries] = useState<BookSeries[]>([])
  const [books, setBooks] = useState<Book[]>([])
  const [selectedSeriesIds, setSelectedSeriesIds] = useState<string[]>([])
  const [existingBookId, setExistingBookId] = useState(initialExistingBookId)
  const [chapterSource, setChapterSource] = useState<"paste" | "upload">("paste")
  const [chapterNumber, setChapterNumber] = useState("")
  const [chapterNumberDirty, setChapterNumberDirty] = useState(false)
  const [chapterTitle, setChapterTitle] = useState("")
  const [chapterText, setChapterText] = useState("")
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [splitIntoChapters, setSplitIntoChapters] = useState(true)
  const [chunkLongDocuments, setChunkLongDocuments] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [autoExtractCover, setAutoExtractCover] = useState(true)
  const [preserveChapterNumbers, setPreserveChapterNumbers] = useState(false)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [usernameInput, setUsernameInput] = useState("")
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [settingUsername, setSettingUsername] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStage, setUploadStage] = useState<"idle" | "uploading" | "processing">("idle")
  const [error, setError] = useState<string | null>(null)
  const [postImportReview, setPostImportReview] = useState<EditorialReview | null>(null)
  const [postImportPassages, setPostImportPassages] = useState<EditorialReviewPassage[]>([])
  const [postImportSuggestions, setPostImportSuggestions] = useState<AdvisorSuggestion[]>([])
  const [postImportThreads, setPostImportThreads] = useState<PlotThread[]>([])
  const [postImportSynopsis, setPostImportSynopsis] = useState<ManuscriptSynopsis | null>(null)
  const [chapterReports, setChapterReports] = useState<ChapterConsistencyReport[]>([])
  const [reportReady, setReportReady] = useState<{ bookId: string; chapterNum?: number; text: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const coverInputRef = useRef<HTMLInputElement>(null)
  const { theme } = usePreferencesStore()
  const user = useAuthStore((state) => state.user)
  const setBookMode = useBookModeStore((state) => state.setMode)
  const isDark = theme === "dark"
  const visibility: "private" = "private"
  const genre = selectedTags.join(", ")
  const trimmedCustomTag = customTag.trim()
  const shouldShowTagSuggestions = trimmedCustomTag.length >= 2
  const suggestedTags = GENRE_TAGS
    .filter((tag) => !selectedTags.includes(tag))
    .filter((tag) => (shouldShowTagSuggestions ? tagSimilarity(tag, trimmedCustomTag) >= 0.34 : false))
    .sort((a, b) => tagSimilarity(b, trimmedCustomTag) - tagSimilarity(a, trimmedCustomTag))
    .slice(0, TAG_SUGGESTION_LIMIT)

  useEffect(() => {
    booksApi.listSeries().then(setSeries).catch(() => {})
    booksApi.list(true).then(setBooks).catch(() => {})
  }, [])

  useEffect(() => {
    setMode(initialMode)
  }, [initialMode])

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
  }, [files])

  // Auto-set author to email when in author mode
  useEffect(() => {
    if (mode === "author" && !author) {
      const preferred = user?.username || user?.email
      if (preferred) setAuthor(preferred)
    }
  }, [mode, user, author])

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

  const toggleSeries = (seriesId: string) => {
    setSelectedSeriesIds((current) =>
      current.includes(seriesId)
        ? current.filter((item) => item !== seriesId)
        : [...current, seriesId]
    )
  }

  const existingAuthorBooks = books.filter((book) => book.mode === "author" && !book.hidden_at)
  const selectedExistingBook = existingAuthorBooks.find((book) => book.id === existingBookId) ?? null
  const isManagingExisting = mode === "author" && !!existingBookId
  const needsUsername = mode === "author" && !user?.username
  const hasChapterText = chapterText.trim().length > 0
  const hasChapterFiles = files.length > 0
  const canSubmitExistingImport = chapterSource === "paste" ? hasChapterText : hasChapterFiles

  useEffect(() => {
    if (!isManagingExisting || replaceExisting || chapterNumberDirty) return
    const nextChapter = (selectedExistingBook?.total_chapters ?? 0) + 1
    if (nextChapter > 0) {
      setChapterNumber(String(nextChapter))
    }
  }, [chapterNumberDirty, isManagingExisting, replaceExisting, selectedExistingBook])

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

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (isManagingExisting && !canSubmitExistingImport) {
      setError(chapterSource === "paste" ? "Paste a chapter before processing it." : "Please select a chapter file.")
      return
    }
    if (!isManagingExisting && files.length === 0) {
      setError("Please select at least one file")
      return
    }

    setUploading(true)
    setUploadProgress(0)
    setUploadStage("uploading")
    resetImportFeedback()
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
          files: chapterSource === "upload" ? files : undefined,
        })
        bookId = response.book_id
        setBookMode(response.book_id, "author")
        capture("book_uploaded", {
          mode: "author",
          kind: chapterSource === "paste" ? "single_chapter_paste" : "manuscript_import",
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
        await booksApi.list(true).then(setBooks).catch(() => {})
        return
      } else {
        const primaryFile = files[0]
        const filename = (primaryFile?.name || "").toLowerCase()
        const format = filename.endsWith(".pdf") ? "pdf" : filename.endsWith(".epub") ? "epub" : "other"
        const response = await booksApi.upload(primaryFile, title, genre || undefined, author || undefined, {
          visibility,
          seriesIds: selectedSeriesIds,
          autoExtractCover,
          preserveChapterNumbers,
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
          has_cover_file: Boolean(coverFile) && !autoExtractCover,
          preserve_chapter_numbers: preserveChapterNumbers,
          tag_count: selectedTags.length,
          in_series: selectedSeriesIds.length > 0,
        })
      }
      setUploadStage("processing")
      setUploadProgress(100)
      onClose()
    } catch {
      setError("Upload failed. Please try again.")
    } finally {
      setUploading(false)
      setUploadStage("idle")
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
  const shellClassName = `flex ${isInline ? "min-h-0" : "max-h-[90vh]"} w-full ${postImportReview || isManagingExisting ? "max-w-5xl" : "max-w-md"} flex-col overflow-hidden rounded-2xl border p-6 shadow-2xl transition-colors ${
    isDark
      ? isInline
        ? "border-white/10 bg-[#0B0B0B] text-slate-100 shadow-[0_30px_80px_-35px_rgba(0,0,0,0.8)]"
        : "border-white/10 bg-[#0B0B0B]/90 backdrop-blur-xl text-slate-100 shadow-[0_30px_80px_-35px_rgba(0,0,0,0.9)]"
      : "border-black/5 bg-white text-slate-950"
  }`

  const content = (
      <div className={shellClassName}>
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">{isManagingExisting ? "Add New Chapter" : "Upload Book"}</h2>
            <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              {isManagingExisting
                ? "Paste or upload one chapter, process it incrementally, and review what changed before moving on."
                : "Add a new book to your workspace."}
            </p>
          </div>
          <button
            onClick={onClose}
            className={`text-xl transition-colors ${
              isDark ? "text-slate-400 hover:text-white" : "text-slate-400 hover:text-slate-700"
            }`}
            aria-label="Close upload modal"
          >
            ×
          </button>
        </div>

        <form onSubmit={submit} className="reader-scrollbar min-h-0 flex-1 overflow-y-auto pr-1">
          <div className="flex flex-col gap-4">
          {!isManagingExisting ? (
            <input
              type="text"
              placeholder="Title"
              value={title}
              onChange={e => setTitle(e.target.value)}
              required
              className={`rounded-lg border px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                isDark
                  ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500"
                  : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400"
              }`}
            />
          ) : null}

          {!isManagingExisting ? (
            <input
              type="text"
              placeholder="Author (optional)"
              value={author}
              onChange={e => setAuthor(e.target.value)}
              className={`rounded-lg border px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                isDark
                  ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500"
                  : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400"
              }`}
            />
          ) : null}

          <div className={`rounded-xl border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Mode</p>
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
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setMode(value)}
                    className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${
                      active
                        ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950 shadow-sm"
                        : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white/70"
                    }`}
                  >
                    {value === "reader" ? "Reading mode" : "Author mode"}
                  </button>
                )
              })}
            </div>
            {mode === "author" && !user?.username ? (
              <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-amber-500/30 bg-amber-500/10" : "border-amber-300 bg-amber-50"}`}>
                <p className={`text-sm font-medium mb-2 ${isDark ? "text-amber-200" : "text-amber-800"}`}>Set your username to use Author mode</p>
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
                <p className={`mt-2 text-xs ${isDark ? "text-amber-300/70" : "text-amber-600"}`}>Username can only be set once and cannot be changed later.</p>
              </div>
            ) : null}
            {mode === "author" && existingAuthorBooks.length > 0 ? (
              <div className="mt-4">
                <label className={`mb-2 block text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Manage existing author upload
                </label>
                <select
                  value={existingBookId}
                  onChange={(e) => {
                    setExistingBookId(e.target.value)
                    setChapterNumberDirty(false)
                  }}
                  className={`w-full rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-gray-300 bg-white text-slate-950"}`}
                >
                  <option value="">Create a new upload</option>
                  {existingAuthorBooks.map((book) => (
                    <option key={book.id} value={book.id}>{book.title}</option>
                  ))}
                </select>
              </div>
            ) : null}
          </div>

          {/* 2. The Input & Dynamic Suggestion Area */}
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
                  <p className={`text-[10px] font-bold uppercase tracking-wider ${isDark ? "text-slate-500" : "text-slate-500"}`}>
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

          <div className={`rounded-xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-gray-200 bg-gray-50 text-slate-600"}`}>
            Upload visibility: private
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
            <div className={`rounded-2xl border p-5 ${isDark ? "border-indigo-500/20 bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.18),transparent_45%),rgba(255,255,255,0.03)]" : "border-indigo-200 bg-[radial-gradient(circle_at_top_left,rgba(224,231,255,0.9),transparent_45%),#f8fafc]"}`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-indigo-700"}`}>Single-chapter workflow</p>
                  <p className={`mt-2 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    LoreVia will attach this chapter to {selectedExistingBook ? `"${selectedExistingBook.title}"` : "your selected manuscript"}, update character memory and thread data, then surface continuity risks from the fresh ingest.
                  </p>
                </div>
                <div className={`rounded-xl border px-4 py-3 text-xs ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-white bg-white text-stone-600 shadow-sm"}`}>
                  <p className="font-semibold">After processing</p>
                  <p className="mt-1">You’ll get a chapter summary, new-character changes, thread movement, and continuity review.</p>
                </div>
              </div>

              <div className={`mt-4 inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-white/5" : "border border-stone-200 bg-white/80"}`}>
                {([
                  { value: "paste", label: "Paste chapter" },
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
                          ? isDark ? "bg-white text-slate-950" : "bg-indigo-600 text-white shadow-sm"
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
                      placeholder="Chapter number"
                      value={chapterNumber}
                      onChange={(e) => {
                        setChapterNumber(e.target.value)
                        setChapterNumberDirty(true)
                      }}
                      className={`rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-gray-300 bg-white text-slate-950"}`}
                    />
                    <label className={`flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-gray-300 bg-white text-slate-700"}`}>
                      <input type="checkbox" checked={replaceExisting} onChange={(e) => setReplaceExisting(e.target.checked)} />
                      Replace chapter
                    </label>
                  </div>

                  {chapterSource === "paste" ? (
                    <>
                      <input
                        type="text"
                        placeholder="Chapter title (optional)"
                        value={chapterTitle}
                        onChange={(e) => setChapterTitle(e.target.value)}
                        className={`rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500" : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400"}`}
                      />
                      <textarea
                        value={chapterText}
                        onChange={(e) => setChapterText(e.target.value)}
                        placeholder="Paste one chapter here. LoreVia will save it into the manuscript, refresh character profiles, and immediately run continuity checks."
                        rows={14}
                        className={`min-h-[280px] rounded-xl border px-3 py-3 text-sm leading-6 outline-none transition ${isDark ? "border-white/10 bg-black/20 text-slate-100 placeholder:text-slate-500 focus:border-indigo-400/50" : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400 focus:border-indigo-400"}`}
                      />
                      <div className={`flex items-center justify-between text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        <span>{chapterText.trim() ? `${chapterText.trim().split(/\s+/).length} words ready` : "No chapter text pasted yet"}</span>
                        <span>{replaceExisting ? "Will replace the selected chapter number" : "Will append if the chapter number is new"}</span>
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
                        accept=".pdf,.epub,.docx,.txt,.md"
                        className="hidden"
                        onChange={e => setFiles(Array.from(e.target.files ?? []))}
                      />
                      {files.length > 0 ? (
                        <p className={`text-sm ${isDark ? "text-slate-100" : "text-slate-700"}`}>
                          {files.length === 1 ? files[0].name : `${files.length} files selected`}
                        </p>
                      ) : (
                        <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-400"}`}>
                          Click to select a chapter file. Use PDF, EPUB, DOCX, TXT, or Markdown.
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-white bg-white shadow-sm"}`}>
                    <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Processing options</p>
                    <div className="mt-3 flex flex-wrap gap-3">
                      <label className={`flex items-center gap-2 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                        <input type="checkbox" checked={splitIntoChapters} onChange={(e) => setSplitIntoChapters(e.target.checked)} />
                        Split PDFs into chapters
                      </label>
                      <label className={`flex items-center gap-2 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                        <input type="checkbox" checked={chunkLongDocuments} onChange={(e) => setChunkLongDocuments(e.target.checked)} />
                        Chunk long files
                      </label>
                    </div>
                    <div className={`mt-4 rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
                      <p className="font-semibold">What LoreVia updates</p>
                      <p className="mt-1">Character state, relationship extraction, plot-thread analysis, and chapter-level continuity flags are all rerun from this chapter ingest.</p>
                      {!replaceExisting && selectedExistingBook ? (
                        <p className="mt-2 text-xs opacity-80">
                          Suggested next chapter: {(selectedExistingBook.total_chapters ?? 0) + 1}
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
                        Choose a chapter number, paste or upload a single chapter, and LoreVia will return a focused report instead of making you dig through the whole manuscript again.
                      </p>
                    </div>
                  )}

                  {chapterReports.some((report) => report.continuity_flags.length > 0) ? (
                    <div className={`rounded-xl border p-4 ${isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
                      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-amber-200" : "text-amber-800"}`}>Fresh chapter continuity flags</p>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                        These were surfaced directly from the chapter you just imported, after LoreVia refreshed stored character and story state.
                      </p>
                      <div className="mt-3 space-y-2">
                        {chapterReports.flatMap((report) =>
                          report.continuity_flags.map((flag, index) => (
                            <div key={`${report.chapter_number}-fresh-${index}`} className={`rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-white bg-white text-stone-700"}`}>
                              <p className="font-semibold">Chapter {report.chapter_number}{report.chapter_title ? ` - ${report.chapter_title}` : ""}</p>
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
            <div
              onClick={() => inputRef.current?.click()}
              className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
                isDark
                  ? "border-white/15 bg-white/[0.03] hover:border-indigo-400"
                  : "border-gray-300 bg-white hover:border-indigo-400"
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                multiple={false}
                accept=".pdf,.epub"
                className="hidden"
                onChange={e => setFiles(Array.from(e.target.files ?? []))}
              />
              {files.length > 0 ? (
                <p className={`text-sm ${isDark ? "text-slate-100" : "text-slate-700"}`}>
                  {files[0].name}
                </p>
              ) : (
                <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-400"}`}>
                  Click to select PDF or EPUB
                </p>
              )}
            </div>
          ) : null}

          {!isManagingExisting ? (
          <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
            <div className="mb-4">
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={preserveChapterNumbers}
                  onChange={(e) => setPreserveChapterNumbers(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-900"}`}>Preserve chapter numbers from the source file</p>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    Best for novels that already have clean Chapter 1, 2, 3 headings. LoreVia will keep whole detected chapters together and only fall back to the current sequential chunking path if the source numbering is inconsistent.
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
                <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Enabled by default for PDFs. Turn this off if you want to upload a separate cover image instead.
                </p>
              </div>
            </label>
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

          <button
            type="submit"
            disabled={uploading || needsUsername || (isManagingExisting && !canSubmitExistingImport)}
            className="rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            {uploading
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
                  : "Upload & Process"}
          </button>

          {chapterReports.length > 0 ? (
            <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-50"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Chapter consistency report</p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>Generated from the latest import so you can review the chapter in under 30 seconds.</p>
                </div>
              </div>

              <div className="mt-4 space-y-4">
                {chapterReports.map((report) => (
                  <div key={`${report.chapter_number}-${report.chapter_title ?? "untitled"}`} className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-white bg-white"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                          Chapter {report.chapter_number}{report.chapter_title ? ` - ${report.chapter_title}` : ""}
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
                              <span key={point} className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-700"}`}>{point}</span>
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
                        <p className="mt-1 text-xs opacity-80">Introduced in chapter {thread.introduced_at ?? "?"} · {thread.status}</p>
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
        </form>
      </div>
  )

  return isInline ? content : (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
      {content}
    </div>
  )
}

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
