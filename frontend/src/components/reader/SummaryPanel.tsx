"use client"
import { useState, useEffect } from "react"
import { readerApi } from "@/lib/api/reader"
import type { ChapterSummary, SummaryMode } from "@/types/reader"
import { SUMMARY_MODE_LABELS } from "@/lib/constants"

interface Props {
  bookId: string
  chapterNum: number
  onClose: () => void
  theme: "light" | "dark"
}

export function SummaryPanel({ bookId, chapterNum, onClose, theme }: Props) {
  const [mode, setMode] = useState<SummaryMode>("short")
  const [summary, setSummary] = useState<ChapterSummary | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    readerApi.getSummary(bookId, chapterNum, mode)
      .then(setSummary)
      .finally(() => setLoading(false))
  }, [bookId, chapterNum, mode])

  const shellClass = theme === "dark" ? "bg-black text-white border border-white/10" : "bg-white text-black"
  const tabActiveClass = theme === "dark" ? "bg-white text-black font-medium" : "bg-black text-white font-medium"
  const tabIdleClass = theme === "dark" ? "text-gray-300 hover:bg-white/10" : "text-gray-500 hover:bg-gray-100"
  const normalized = summary ? normalizeSummary(summary) : null

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className={`rounded-2xl w-full max-w-lg max-h-[80vh] flex flex-col transition-colors ${shellClass}`}>
        <div className={theme === "dark" ? "flex items-center justify-between px-5 py-4 border-b border-white/10" : "flex items-center justify-between px-5 py-4 border-b border-gray-100"}>
          <h2 className="font-semibold">Chapter {chapterNum} Summary</h2>
          <button onClick={onClose} className={theme === "dark" ? "text-gray-500 hover:text-white text-xl" : "text-gray-400 hover:text-gray-600 text-xl"}>×</button>
        </div>
        <div className="flex gap-1 px-5 pt-4">
          {(Object.entries(SUMMARY_MODE_LABELS) as [SummaryMode, string][]).map(([m, label]) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                mode === m ? tabActiveClass : tabIdleClass
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex justify-center py-8"><div className="w-5 h-5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" /></div>
          ) : normalized ? (
            <div>
              <p className={theme === "dark" ? "text-sm text-gray-100 leading-relaxed whitespace-pre-wrap" : "text-sm text-gray-700 leading-relaxed whitespace-pre-wrap"}>
                {normalized.content}
              </p>

              {normalized.key_events && normalized.key_events.length > 0 && (
                <div className="mt-4">
                  <p className={theme === "dark" ? "text-xs font-medium text-gray-400 uppercase tracking-wide mb-2" : "text-xs font-medium text-gray-500 uppercase tracking-wide mb-2"}>
                    Key Events
                  </p>
                  {normalized.key_events.map((e, i) => (
                    <p key={i} className={theme === "dark" ? "text-sm text-gray-300 mb-1" : "text-sm text-gray-600 mb-1"}>
                      - {e.event}
                    </p>
                  ))}
                </div>
              )}

              {normalized.char_changes && normalized.char_changes.length > 0 && (
                <div className="mt-4">
                  <p className={theme === "dark" ? "text-xs font-medium text-gray-400 uppercase tracking-wide mb-2" : "text-xs font-medium text-gray-500 uppercase tracking-wide mb-2"}>
                    Character Changes
                  </p>
                  {normalized.char_changes.map((e, i) => (
                    <p key={i} className={theme === "dark" ? "text-sm text-gray-300 mb-1" : "text-sm text-gray-600 mb-1"}>
                      - {e.character}: {e.change}
                    </p>
                  ))}
                </div>
              )}

              {normalized.clues && normalized.clues.length > 0 && (
                <div className="mt-4">
                  <p className={theme === "dark" ? "text-xs font-medium text-gray-400 uppercase tracking-wide mb-2" : "text-xs font-medium text-gray-500 uppercase tracking-wide mb-2"}>
                    Clues
                  </p>
                  {normalized.clues.map((e, i) => (
                    <p key={i} className={theme === "dark" ? "text-sm text-gray-300 mb-1" : "text-sm text-gray-600 mb-1"}>
                      - {e.clue}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className={theme === "dark" ? "text-sm text-gray-500 text-center py-8" : "text-sm text-gray-400 text-center py-8"}>
              Summary not available yet
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function normalizeSummary(summary: ChapterSummary): ChapterSummary {
  const trimmed = summary.content.trim()
  if (!trimmed.startsWith("{") && !trimmed.startsWith("```")) {
    return {
      ...summary,
      key_events: summary.key_events ?? [],
      char_changes: summary.char_changes ?? [],
      clues: summary.clues ?? [],
    }
  }

  try {
    const stripped = trimmed
      .replace(/^```json\s*/i, "")
      .replace(/^```\s*/i, "")
      .replace(/\s*```$/, "")
    const parsed = JSON.parse(stripped)
    if (parsed && typeof parsed === "object") {
      return {
        content: parsed.summary ?? summary.content,
        key_events: parsed.key_events ?? summary.key_events ?? [],
        char_changes: parsed.char_changes ?? summary.char_changes ?? [],
        clues: parsed.clues ?? summary.clues ?? [],
      }
    }
  } catch {}

  return {
    ...summary,
    key_events: summary.key_events ?? [],
    char_changes: summary.char_changes ?? [],
    clues: summary.clues ?? [],
  }
}
