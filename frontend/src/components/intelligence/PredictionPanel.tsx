"use client"
import { useState } from "react"
import { intelligenceApi } from "@/lib/api/intelligence"

interface Props { bookId: string; currentChapter: number }

export function PredictionPanel({ bookId, currentChapter }: Props) {
  const [question, setQuestion] = useState("")
  const [answer, setAnswer] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ask = async () => {
    if (!question.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await intelligenceApi.answer(bookId, question, currentChapter)
      setAnswer(res.answer)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "Answer failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-xs text-gray-500 mb-2">
          Ask a grounded question based only on what you have already read up to chapter {currentChapter}.
        </p>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === "Enter" && ask()}
            placeholder='e.g. "Why did Ivan leave?"'
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            onClick={ask}
            disabled={loading || !question.trim()}
            className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "..." : "Ask"}
          </button>
        </div>
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
      </div>

      {answer && (
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-2 uppercase tracking-wide">Contextual answer</p>
          <p className="text-sm text-gray-700 leading-relaxed">{answer}</p>
        </div>
      )}
    </div>
  )
}
