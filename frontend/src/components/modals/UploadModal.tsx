"use client"
import { useEffect, useRef, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { useBookModeStore, type BookMode } from "@/lib/stores/bookModeStore"
import { GENRE_TAGS } from "@/lib/constants/genreTags"
import type { BookSeries } from "@/types/book"

const MAX_TAGS = 8

export function UploadModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("")
  const [author, setAuthor] = useState("")
  const [mode, setMode] = useState<BookMode>("reader")
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [customTag, setCustomTag] = useState("")
  const [series, setSeries] = useState<BookSeries[]>([])
  const [selectedSeriesIds, setSelectedSeriesIds] = useState<string[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [autoExtractCover, setAutoExtractCover] = useState(true)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStage, setUploadStage] = useState<"idle" | "uploading" | "processing">("idle")
  const [error, setError] = useState<string | null>(null)
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

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError("Please select a file")
      return
    }

    setUploading(true)
    setUploadProgress(0)
    setUploadStage("uploading")
    setError(null)
    try {
      const response = await booksApi.upload(file, title, genre || undefined, author || undefined, {
        visibility,
        seriesIds: selectedSeriesIds,
        autoExtractCover,
        coverFile: autoExtractCover ? null : coverFile,
        mode,
        onProgress: (percent) => {
          setUploadProgress(percent)
        },
      })
      const bookId = typeof response?.book_id === "string" ? response.book_id : null
      if (bookId) setBookMode(bookId, mode)
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4">
      <div
        className={`flex max-h-[90vh] w-full max-w-md flex-col overflow-hidden rounded-2xl border p-6 shadow-2xl transition-colors ${
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
              accept=".pdf,.epub"
              className="hidden"
              onChange={e => setFile(e.target.files?.[0] ?? null)}
            />
            {file ? (
              <p className={`text-sm ${isDark ? "text-slate-100" : "text-slate-700"}`}>{file.name}</p>
            ) : (
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-400"}`}>Click to select PDF or EPUB</p>
            )}
          </div>

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
