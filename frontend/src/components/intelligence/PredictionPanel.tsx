"use client"
import { useState } from "react"
import { intelligenceApi } from "@/lib/api/intelligence"
import type { Theory } from "@/types/intelligence"

interface Props { bookId: string; currentChapter: number }

export function PredictionPanel({ bookId, currentChapter }: Props) {
  const [question, setQuestion] = useState("")
  const [theories, setTheories] = useState<Theory[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ask = async () => {
    if (!question.trim()) return
    setLoading(true); setError(null)
    try {
      const res = await intelligenceApi.predict(bookId, question, currentChapter)
      setTheories(res.theories)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "Prediction failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-xs text-gray-500 mb-2">
          Ask a prediction question based on what you've read so far (up to ch. {currentChapter}).
        </p>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === "Enter" && ask()}
            placeholder='e.g. "Who is likely the traitor?"'
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            onClick={ask} disabled={loading || !question.trim()}
            className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "..." : "Ask"}
          </button>
        </div>
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
      </div>

      {theories.length > 0 && (
        <div className="flex flex-col gap-3">
          {theories.map((t, i) => (
            <div key={i} className="bg-white border border-gray-100 rounded-xl p-4">
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="text-sm font-medium text-gray-900">{t.theory}</p>
                <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 font-medium ${
                  t.confidence >= 0.7 ? "bg-green-100 text-green-700" :
                  t.confidence >= 0.4 ? "bg-amber-100 text-amber-700" :
                  "bg-gray-100 text-gray-600"
                }`}>
                  {Math.round(t.confidence * 100)}%
                </span>
              </div>
              <p className="text-xs text-gray-600 mb-2">{t.reasoning}</p>
              {t.evidence.length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 mb-1">Evidence:</p>
                  {t.evidence.map((e, j) => (
                    <p key={j} className="text-xs text-gray-500 before:content-['•'] before:mr-1">{e}</p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
