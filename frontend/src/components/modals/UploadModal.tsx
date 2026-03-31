"use client"
import { useRef, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const GENRES = ["anime", "light novel", "fantasy", "sci-fi", "romance", "thriller", "realistic", "horror", "other"]

export function UploadModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("")
  const [genre, setGenre] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError("Please select a file")
      return
    }

    setUploading(true)
    setError(null)
    try {
      await booksApi.upload(file, title, genre || undefined)
      onClose()
    } catch {
      setError("Upload failed. Please try again.")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4">
      <div
        className={`w-full max-w-md rounded-2xl border p-6 shadow-2xl transition-colors ${
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

        <form onSubmit={submit} className="flex flex-col gap-4">
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

          <select
            value={genre}
            onChange={e => setGenre(e.target.value)}
            className={`rounded-lg border px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
              isDark
                ? "border-white/10 bg-white/5 text-slate-100"
                : "border-gray-300 bg-white text-slate-950"
            }`}
          >
            <option value="">Genre (optional)</option>
            {GENRES.map(g => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>

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

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={uploading}
            className="rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Upload & Process"}
          </button>
        </form>
      </div>
    </div>
  )
}
