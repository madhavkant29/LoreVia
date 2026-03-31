"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { readerApi } from "@/lib/api/reader"
import { PredictionPanel } from "@/components/intelligence/PredictionPanel"

export default function AskPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [currentChapter, setCurrentChapter] = useState(1)

  useEffect(() => {
    readerApi.getProgress(bookId).then((progress) => {
      setCurrentChapter(Math.max(1, progress?.current_chapter ?? 1))
    }).catch(() => {})
  }, [bookId])

  return (
    <div className="min-h-screen bg-white px-4 py-8 text-black">
      <div className="mx-auto max-w-3xl">
        <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">{"<- Back"}</button>
        <h1 className="mt-4 text-3xl font-semibold">Ask the Book</h1>
        <p className="mt-2 text-sm text-gray-500">Answers are grounded in what you have already read and will not speculate beyond your current chapter.</p>
        <div className="mt-8 rounded-2xl border border-gray-200 bg-white p-6">
          <PredictionPanel bookId={bookId} currentChapter={currentChapter} />
        </div>
      </div>
    </div>
  )
}
