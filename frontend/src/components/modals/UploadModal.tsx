"use client"
import { useState, useRef } from "react"
import { booksApi } from "@/lib/api/books"

const GENRES = ["anime", "light novel", "fantasy", "sci-fi", "romance", "thriller", "realistic", "horror", "other"]

export function UploadModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("")
  const [genre, setGenre] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { setError("Please select a file"); return }
    setUploading(true); setError(null)
    try {
      await booksApi.upload(file, title, genre || undefined)
      onClose()
    } catch { setError("Upload failed. Please try again.") }
    finally { setUploading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Upload Book</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <input type="text" placeholder="Title" value={title} onChange={e => setTitle(e.target.value)} required
            className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <select value={genre} onChange={e => setGenre(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
            <option value="">Genre (optional)</option>
            {GENRES.map(g => <option key={g} value={g}>{g}</option>)}
          </select>
          <div onClick={() => inputRef.current?.click()}
            className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-indigo-400 transition-colors">
            <input ref={inputRef} type="file" accept=".pdf,.epub" className="hidden"
              onChange={e => setFile(e.target.files?.[0] ?? null)} />
            {file ? <p className="text-sm text-gray-700">{file.name}</p> : <p className="text-sm text-gray-400">Click to select PDF or EPUB</p>}
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button type="submit" disabled={uploading}
            className="bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
            {uploading ? "Uploading..." : "Upload & Process"}
          </button>
        </form>
      </div>
    </div>
  )
}
