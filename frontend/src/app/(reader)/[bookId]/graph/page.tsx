"use client"
import { useParams, useRouter } from "next/navigation"
import { RelationshipGraph } from "@/components/intelligence/RelationshipGraph"
import { useEffect, useState } from "react"
import { readerApi } from "@/lib/api/reader"

export default function GraphPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [chapter, setChapter] = useState(999)

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">← Back</button>
        <h1 className="text-xl font-semibold">Relationship Graph</h1>
        <div className="ml-auto flex items-center gap-2 text-sm text-gray-500">
          <span>Up to chapter</span>
          <input type="number" value={chapter} min={1} onChange={e => setChapter(Number(e.target.value))}
            className="w-16 border border-gray-300 rounded px-2 py-1 text-sm" />
        </div>
      </div>
      <RelationshipGraph bookId={bookId} upToChapter={chapter} />
    </div>
  )
}
