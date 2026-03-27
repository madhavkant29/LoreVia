"use client"
import Link from "next/link"

interface Props {
  bookId: string
  chapterNum: number
  totalChapters: number | null
  onSummary: () => void
}

export function ReaderToolbar({ bookId, chapterNum, totalChapters, onSummary }: Props) {
  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white shrink-0">
      <div className="flex items-center gap-3">
        <Link href={`/${bookId}`} className="text-sm text-gray-400 hover:text-gray-600">← Overview</Link>
        <span className="text-sm text-gray-500">
          Ch. {chapterNum}{totalChapters ? ` of ${totalChapters}` : ""}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={onSummary}
          className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors">
          Summary
        </button>
        <Link href={`/${bookId}/search`}
          className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors">
          Search
        </Link>
        <Link href={`/${bookId}/graph`}
          className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors">
          Graph
        </Link>
        {chapterNum > 1 && (
          <Link href={`/${bookId}/chapter/${chapterNum - 1}`}
            className="text-sm px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50">←</Link>
        )}
        <Link href={`/${bookId}/chapter/${chapterNum + 1}`}
          className="text-sm px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50">→</Link>
      </div>
    </header>
  )
}
