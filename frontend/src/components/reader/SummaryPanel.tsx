"use client"
import { useState, useEffect } from "react"
import { readerApi } from "@/lib/api/reader"
import type { ChapterSummary, SummaryMode } from "@/types/reader"
import { SUMMARY_MODE_LABELS } from "@/lib/constants"

interface Props { bookId: string; chapterNum: number; onClose: () => void }

export function SummaryPanel({ bookId, chapterNum, onClose }: Props) {
  const [mode, setMode] = useState<SummaryMode>("short")
  const [summary, setSummary] = useState<ChapterSummary | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    readerApi.getSummary(bookId, chapterNum, mode)
      .then(setSummary)
      .finally(() => setLoading(false))
  }, [bookId, chapterNum, mode])

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold">Chapter {chapterNum} Summary</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>
        <div className="flex gap-1 px-5 pt-4">
          {(Object.entries(SUMMARY_MODE_LABELS) as [SummaryMode, string][]).map(([m, label]) => (
            <button key={m} onClick={() => setMode(m)}
              className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                mode === m ? "bg-indigo-100 text-indigo-700 font-medium" : "text-gray-500 hover:bg-gray-100"
              }`}>
              {label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex justify-center py-8"><div className="w-5 h-5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" /></div>
          ) : summary ? (
            <div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{summary.content}</p>
              {summary.key_events && summary.key_events.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Key Events</p>
                  {summary.key_events.map((e, i) => (
                    <p key={i} className="text-sm text-gray-600 mb-1">• {e.event}</p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400 text-center py-8">Summary not available yet</p>
          )}
        </div>
      </div>
    </div>
  )
}
