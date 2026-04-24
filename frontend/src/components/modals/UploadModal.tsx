"use client"
import { useEffect, useRef, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { useBookModeStore, type BookMode } from "@/lib/stores/bookModeStore"
import { GENRE_TAGS } from "@/lib/constants/genreTags"
import { capture } from "@/lib/analytics/posthog"
import type { Book, BookSeries, ChapterConsistencyReport } from "@/types/book"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"

const MAX_TAGS = 8

export function UploadModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("")
  const [author, setAuthor] = useState("")
  const [mode, setMode] = useState<BookMode>("reader")
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [customTag, setCustomTag] = useState("")
  const [series, setSeries] = useState<BookSeries[]>([])
  const [books, setBooks] = useState<Book[]>([])
  const [selectedSeriesIds, setSelectedSeriesIds] = useState<string[]>([])
  const [existingBookId, setExistingBookId] = useState("")
  const [chapterNumber, setChapterNumber] = useState("")
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [splitIntoChapters, setSplitIntoChapters] = useState(true)
  const [chunkLongDocuments, setChunkLongDocuments] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [autoExtractCover, setAutoExtractCover] = useState(true)
  const [coverFile, setCoverFile] = useState<File | null>(null)
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
  const setBookMode = useBookModeStore((state) => state.setMode)
  const isDark = theme === "dark"
  const visibility: "private" = "private"
  const genre = selectedTags.join(", ")
  const suggestedTags = GENRE_TAGS.filter((tag) => !selectedTags.includes(tag)).slice(0, 18)

  useEffect(() => {
    booksApi.listSeries().then(setSeries).catch(() => {})
    booksApi.list(true).then(setBooks).catch(() => {})
  }, [])

  const addTag = (rawTag: string) => {
    const tag = normalizeTag(rawTag)
    if (!tag) return
    setSelectedTags((current) => {
      if (current.includes(tag) || current.length >= MAX_TAGS) return current
      return [...current, tag]
    })
  }

  const removeTag = (tag: string) => {
    setSelectedTags((current) => current.filter((item) => item !== tag))
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
  const isManagingExisting = mode === "author" && !!existingBookId

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (files.length === 0) {
      setError("Please select at least one file")
      return
    }

    setUploading(true)
    setUploadProgress(0)
    setUploadStage("uploading")
    setError(null)
    setPostImportReview(null)
    setPostImportPassages([])
    setPostImportSuggestions([])
    setPostImportThreads([])
    setPostImportSynopsis(null)
    setChapterReports([])
    setReportReady(null)
    try {
      let bookId: string | null = null
      if (isManagingExisting) {
        const response = await booksApi.importManuscript(existingBookId, {
          chapterNumber: chapterNumber ? parseInt(chapterNumber) : undefined,
          replaceExisting,
          splitIntoChapters,
          chunkLongDocuments,
          files,
        })
        bookId = response.book_id
        setBookMode(response.book_id, "author")
        capture("book_uploaded", {
          mode: "author",
          kind: "manuscript_import",
          file_count: files.length,
          replace_existing: replaceExisting,
          split_into_chapters: splitIntoChapters,
          chunk_long_documents: chunkLongDocuments,
        })
        setChapterReports(response.chapter_reports ?? [])
        const importedChapter = response.imported_chapters[0]
        if (importedChapter) {
          try {
            const chapterData = await readerApi.getChapter(response.book_id, importedChapter)
            const recoveredText = chapterData.text_content || ""
            await loadPostImportReview(response.book_id, importedChapter, recoveredText)
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4">
      <div
        className={`flex max-h-[90vh] w-full ${postImportReview ? "max-w-5xl" : "max-w-md"} flex-col overflow-hidden rounded-2xl border p-6 shadow-2xl transition-colors ${
          isDark
            ? "border-white/10 bg-[#0f172a] text-slate-100"
            : "border-black/5 bg-white text-slate-950"
        }`}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Upload Book</h2>
            <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              Add a new book to your workspace.
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
            {mode === "author" && existingAuthorBooks.length > 0 ? (
              <div className="mt-4">
                <label className={`mb-2 block text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Manage existing author upload
                </label>
                <select
                  value={existingBookId}
                  onChange={(e) => setExistingBookId(e.target.value)}
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

          <div className={`rounded-xl border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-300 bg-gray-50"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Genres and tags</p>
              <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{selectedTags.length}/{MAX_TAGS}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedTags.length > 0 ? selectedTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => removeTag(tag)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${isDark ? "bg-indigo-400/15 text-indigo-100 hover:bg-indigo-400/25" : "bg-indigo-100 text-indigo-800 hover:bg-indigo-200"}`}
                >
                  {tag} ×
                </button>
              )) : (
                <p className={`text-sm ${isDark ? "text-slate-500" : "text-slate-400"}`}>Pick suggested tags or add your own.</p>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <input
                type="text"
                list="genre-tags"
                value={customTag}
                onChange={e => setCustomTag(e.target.value)}
                placeholder="Add custom genre or mood"
                className={`flex-1 rounded-lg border px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                  isDark
                    ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500"
                    : "border-gray-300 bg-white text-slate-950 placeholder:text-slate-400"
                }`}
              />
              <button
                type="button"
                onClick={addCustomTag}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition ${isDark ? "bg-white/10 text-white hover:bg-white/15" : "bg-slate-900 text-white hover:bg-slate-800"}`}
              >
                Add
              </button>
            </div>
            <datalist id="genre-tags">
              {GENRE_TAGS.map((tag) => (
                <option key={tag} value={tag} />
              ))}
            </datalist>
            <div className="mt-4 flex flex-wrap gap-2">
              {suggestedTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => addTag(tag)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${isDark ? "border-white/10 text-slate-300 hover:bg-white/5" : "border-slate-300 text-slate-700 hover:bg-white"}`}
                >
                  + {tag}
                </button>
              ))}
            </div>
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
            <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  type="number"
                  min={1}
                  placeholder="Chapter number"
                  value={chapterNumber}
                  onChange={(e) => setChapterNumber(e.target.value)}
                  className={`rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-gray-300 bg-white text-slate-950"}`}
                />
                <label className={`flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-gray-300 bg-white text-slate-700"}`}>
                  <input type="checkbox" checked={replaceExisting} onChange={(e) => setReplaceExisting(e.target.checked)} />
                  Replace chapter
                </label>
              </div>
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
            </div>
          ) : null}

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
              multiple={isManagingExisting}
              accept={isManagingExisting ? ".pdf,.epub,.docx,.txt,.md" : ".pdf,.epub"}
              className="hidden"
              onChange={e => setFiles(Array.from(e.target.files ?? []))}
            />
            {files.length > 0 ? (
              <p className={`text-sm ${isDark ? "text-slate-100" : "text-slate-700"}`}>
                {files.length === 1 ? files[0].name : `${files.length} files selected`}
              </p>
            ) : (
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-400"}`}>
                {isManagingExisting ? "Click to select chapter files or a folder batch" : "Click to select PDF or EPUB"}
              </p>
            )}
          </div>

          {!isManagingExisting ? (
          <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={autoExtractCover}
                onChange={(e) => setAutoExtractCover(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <div>
                <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-900"}`}>Use the first PDF page as the book cover</p>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Enabled by default for PDFs. Turn this off if you want to upload a separate cover image instead.
                </p>
              </div>
            </label>

            {!autoExtractCover ? (
              <div className="mt-4">
                <input
                  ref={coverInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={(e) => setCoverFile(e.target.files?.[0] ?? null)}
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
                  : "Your book upload finished. Parsing and AI extraction continue in the background."}
              </p>
            </div>
          ) : null}

          <button
            type="submit"
            disabled={uploading}
            className="rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            {uploading
              ? uploadStage === "uploading"
                ? "Uploading..."
                : "Starting processing..."
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
                    <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Continuity issues</p>
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
    </div>
  )
}

function normalizeTag(rawTag: string): string {
  return rawTag
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
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
