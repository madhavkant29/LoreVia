"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import type { Book } from "@/types/book"
import { RecallCard } from "@/components/intelligence/RecallCard"
import { useRecall } from "@/lib/hooks/useRecall"

export default function BookOverviewPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [book, setBook] = useState<Book | null>(null)
  const [progress, setProgress] = useState<{ current_chapter: number } | null>(null)
  const router = useRouter()
  const { recall, lastChapter, show, dismiss } = useRecall(bookId)

  useEffect(() => {
    booksApi.get(bookId).then(setBook)
    readerApi.getProgress(bookId).then(setProgress).catch(() => {})
  }, [bookId])

  const continueReading = () => {
    const ch = progress?.current_chapter ?? 1
    router.push(`/${bookId}/chapter/${ch}`)
  }

  if (!book) return <div className="flex justify-center py-20 text-gray-400">Loading...</div>

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      {show && recall && (
        <RecallCard recall={recall} lastChapter={lastChapter!} onDismiss={dismiss} onContinue={continueReading} />
      )}
      <h1 className="text-3xl font-bold mb-1">{book.title}</h1>
      {book.author && <p className="text-gray-500 mb-6">by {book.author}</p>}
      <div className="flex gap-3">
        <button onClick={continueReading}
          className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 transition-colors">
          {progress?.current_chapter && progress.current_chapter > 1 ? `Continue — Chapter ${progress.current_chapter}` : "Start Reading"}
        </button>
        <button onClick={() => router.push(`/${bookId}/characters`)}
          className="px-6 py-3 border border-gray-300 rounded-xl font-medium hover:bg-gray-50 transition-colors">
          Characters
        </button>
        <button onClick={() => router.push(`/${bookId}/graph`)}
          className="px-6 py-3 border border-gray-300 rounded-xl font-medium hover:bg-gray-50 transition-colors">
          Relationships
        </button>
      </div>
    </div>
  )
}
