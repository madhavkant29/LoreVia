"use client"
import { useEffect, useState } from "react"
import { booksApi } from "@/lib/api/books"
import type { Book } from "@/types/book"
import { UploadModal } from "@/components/modals/UploadModal"
import Link from "next/link"

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  processing: "bg-amber-100 text-amber-700",
  ready: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-600",
}

export default function LibraryPage() {
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)

  const load = () => booksApi.list().then(setBooks).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold">My Library</h1>
        <button onClick={() => setShowUpload(true)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors">
          + Upload Book
        </button>
      </div>
      {loading ? (
        <div className="text-center py-20 text-gray-400">Loading...</div>
      ) : books.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg mb-2">No books yet</p>
          <p className="text-sm">Upload a PDF or EPUB to get started</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {books.map(book => (
            <Link key={book.id} href={`/${book.id}`}
              className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between gap-2 mb-2">
                <h2 className="font-medium text-gray-900 line-clamp-2">{book.title}</h2>
                <span className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_COLORS[book.status]}`}>
                  {book.status}
                </span>
              </div>
              {book.author && <p className="text-sm text-gray-500">{book.author}</p>}
              {book.genre && <p className="text-xs text-gray-400 mt-1 capitalize">{book.genre}</p>}
              {book.total_chapters && (
                <p className="text-xs text-gray-400 mt-1">{book.total_chapters} chapters</p>
              )}
            </Link>
          ))}
        </div>
      )}
      {showUpload && <UploadModal onClose={() => { setShowUpload(false); load() }} />}
    </div>
  )
}
