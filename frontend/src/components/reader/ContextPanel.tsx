"use client"
import { useParams } from "next/navigation"
import { useState } from "react"
import type { ContextResult } from "@/types/reader"
import { CharacterCard } from "@/components/characters/CharacterCard"
import { readerApi } from "@/lib/api/reader"

interface Props {
  result: ContextResult
  loading: boolean
  onClose: () => void
  theme: "light" | "dark"
}

export function ContextPanel({ result, loading, onClose, theme }: Props) {
  const { bookId } = useParams<{ bookId: string }>()
  const [savingIndex, setSavingIndex] = useState<number | null>(null)
  const shellClass = theme === "dark"
    ? "border-l border-white/10 bg-black text-white"
    : "border-l border-gray-100 bg-white text-black"
  const borderClass = theme === "dark" ? "border-b border-white/10" : "border-b border-gray-100"
  const cardClass = theme === "dark" ? "bg-white/5" : "bg-gray-50"
  const textClass = theme === "dark" ? "text-gray-300" : "text-gray-700"

  const saveQuote = async (quoteText: string, chapterNumber?: number, characterName?: string | null, index = 0) => {
    setSavingIndex(index)
    try {
      await readerApi.saveQuote(bookId, {
        quote_text: quoteText,
        chapter_number: chapterNumber,
        character_name: characterName,
      })
    } finally {
      setSavingIndex(null)
    }
  }

  return (
    <aside className={`w-80 flex flex-col overflow-hidden shrink-0 transition-colors ${shellClass}`}>
      <div className={`flex items-center justify-between px-4 py-3 ${borderClass}`}>
        <span className={theme === "dark" ? "text-sm font-medium text-white" : "text-sm font-medium text-gray-700"}>Context</span>
        <button onClick={onClose} className={theme === "dark" ? "text-gray-500 hover:text-white text-lg" : "text-gray-400 hover:text-gray-600 text-lg"}>×</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {loading && <div className={theme === "dark" ? "text-center py-8 text-gray-500 text-sm" : "text-center py-8 text-gray-400 text-sm"}>Loading...</div>}
        {!loading && result.type === "character" && result.character && (
          <div>
            <CharacterCard character={result.character} theme={theme} />
            <button
              onClick={() => saveQuote(result.character.description ?? result.character.name, result.character.first_chapter, result.character.name, -1)}
              className={theme === "dark" ? "mt-3 rounded-full border border-white/15 px-3 py-1 text-xs text-gray-300 hover:bg-white/5" : "mt-3 rounded-full border border-gray-300 px-3 py-1 text-xs text-gray-600 hover:bg-gray-100"}
            >
              {savingIndex === -1 ? "Saving..." : "Save note"}
            </button>
            {result.relationships && result.relationships.length > 0 && (
              <div className="mt-4">
                <p className={theme === "dark" ? "text-xs font-medium text-gray-400 mb-2 uppercase tracking-wide" : "text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide"}>
                  Relationships
                </p>
                <div className="flex flex-col gap-2">
                  {result.relationships.map((r, i) => (
                    <div key={i} className={`text-sm rounded-lg p-2 ${cardClass}`}>
                      <span className="capitalize font-medium text-indigo-500">{r.type}</span>
                      {r.description && <p className={`text-xs mt-0.5 ${textClass}`}>{r.description}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {!loading && result.type === "search" && (
          <div className="flex flex-col gap-3">
            {(result.results ?? []).length === 0 && (
              <p className={theme === "dark" ? "text-sm text-gray-500" : "text-sm text-gray-400"}>No relevant passages found.</p>
            )}
            {(result.results ?? []).map((r, i) => (
              <div key={i} className={`rounded-lg p-3 ${cardClass}`}>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <p className="text-xs text-indigo-500">Ch. {r.chapter_num}</p>
                  <button
                    onClick={() => saveQuote(r.text, r.chapter_num, null, i)}
                    className={theme === "dark" ? "rounded-full border border-white/15 px-2 py-0.5 text-[11px] text-gray-300 hover:bg-white/5" : "rounded-full border border-gray-300 px-2 py-0.5 text-[11px] text-gray-600 hover:bg-gray-100"}
                  >
                    {savingIndex === i ? "Saving..." : "Save quote"}
                  </button>
                </div>
                <p className={`text-sm leading-relaxed ${textClass}`}>{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
