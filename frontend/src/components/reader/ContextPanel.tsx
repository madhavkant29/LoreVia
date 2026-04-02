"use client"
import { useMemo, useState } from "react"
import { useParams } from "next/navigation"
import type { ChapterCharacter, ContextResult } from "@/types/reader"
import { CharacterCard } from "@/components/characters/CharacterCard"
import { readerApi } from "@/lib/api/reader"

interface Props {
  result: ContextResult | null
  loading: boolean
  onClose: () => void
  theme: "light" | "dark"
  selectedQuote: string | null
  chapterNumber: number
  chapterTitle: string | null
  characters: ChapterCharacter[]
}

export function ContextPanel({
  result,
  loading,
  onClose,
  theme,
  selectedQuote,
  chapterNumber,
  chapterTitle,
  characters,
}: Props) {
  const { bookId } = useParams<{ bookId: string }>()
  const [savingQuote, setSavingQuote] = useState(false)
  const [quoteCharacter, setQuoteCharacter] = useState("")
  const [quoteNote, setQuoteNote] = useState("")

  const shellClass = theme === "dark"
    ? "border border-white/10 bg-black text-white"
    : "border border-gray-100 bg-white text-black"
  const borderClass = theme === "dark" ? "border-b border-white/10" : "border-b border-gray-100"
  const cardClass = theme === "dark" ? "bg-white/5" : "bg-gray-50"
  const textClass = theme === "dark" ? "text-gray-300" : "text-gray-700"

  const characterOptions = useMemo(
    () => Array.from(new Set((characters ?? []).map((character) => character.name).filter(Boolean))).sort(),
    [characters],
  )

  const saveSelectedQuote = async () => {
    if (!selectedQuote?.trim()) return
    setSavingQuote(true)
    try {
      await readerApi.saveQuote(bookId, {
        quote_text: selectedQuote,
        chapter_number: chapterNumber,
        character_name: quoteCharacter || null,
        note: quoteNote || null,
      })
      setQuoteCharacter("")
      setQuoteNote("")
    } finally {
      setSavingQuote(false)
    }
  }

  return (
    <aside className={`fixed inset-x-0 bottom-0 top-auto z-30 max-h-[78dvh] overflow-hidden rounded-t-3xl shadow-2xl transition-colors md:static md:inset-auto md:max-h-none md:w-80 md:rounded-none md:shadow-none ${shellClass}`}>
      <div className={`flex items-center justify-between px-4 py-3 ${borderClass}`}>
        <span className={theme === "dark" ? "text-sm font-medium text-white" : "text-sm font-medium text-gray-700"}>Context</span>
        <button onClick={onClose} className={theme === "dark" ? "text-lg text-gray-500 hover:text-white" : "text-lg text-gray-400 hover:text-gray-600"}>x</button>
      </div>

      <div className="app-scroll flex h-full flex-col overflow-y-auto p-4">
        {selectedQuote?.trim() ? (
          <div className={`mb-4 rounded-xl border p-3 ${theme === "dark" ? "border-white/10 bg-white/5" : "border-gray-200 bg-gray-50"}`}>
            <p className={theme === "dark" ? "text-xs font-medium uppercase tracking-wide text-gray-400" : "text-xs font-medium uppercase tracking-wide text-gray-500"}>
              Bookmark selected line
            </p>
            <p className={`mt-2 whitespace-pre-wrap text-sm leading-relaxed ${textClass}`}>{selectedQuote.trim()}</p>
            <div className="mt-3 space-y-3">
              <div className={`rounded-lg border px-3 py-2 text-xs ${theme === "dark" ? "border-white/10 text-gray-400" : "border-gray-200 text-gray-500"}`}>
                <span className="font-medium">Chapter:</span> {chapterTitle ? `${chapterNumber} - ${chapterTitle}` : `Chapter ${chapterNumber}`}
              </div>
              <select
                value={quoteCharacter}
                onChange={(e) => setQuoteCharacter(e.target.value)}
                className={`w-full rounded-lg border px-3 py-2 text-sm ${theme === "dark" ? "border-white/10 bg-white/5 text-white" : "border-gray-300 bg-white text-gray-900"}`}
              >
                <option value="">Who said it? (optional)</option>
                {characterOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <textarea
                value={quoteNote}
                onChange={(e) => setQuoteNote(e.target.value)}
                placeholder="Why does this line matter? (optional)"
                rows={3}
                className={`w-full rounded-lg border px-3 py-2 text-sm ${theme === "dark" ? "border-white/10 bg-white/5 text-white placeholder:text-gray-500" : "border-gray-300 bg-white text-gray-900 placeholder:text-gray-400"}`}
              />
              <button
                onClick={saveSelectedQuote}
                className={theme === "dark" ? "w-full rounded-full bg-indigo-500 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-400" : "w-full rounded-full bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500"}
              >
                {savingQuote ? "Saving..." : "Save line bookmark"}
              </button>
            </div>
          </div>
        ) : null}

        {loading && <div className={theme === "dark" ? "py-8 text-center text-sm text-gray-500" : "py-8 text-center text-sm text-gray-400"}>Loading...</div>}

        {!loading && result?.type === "character" && result.character && (
          <div>
            <CharacterCard character={result.character} theme={theme} />
            {result.relationships && result.relationships.length > 0 && (
              <div className="mt-4">
                <p className={theme === "dark" ? "mb-2 text-xs font-medium uppercase tracking-wide text-gray-400" : "mb-2 text-xs font-medium uppercase tracking-wide text-gray-500"}>
                  Relationships
                </p>
                <div className="flex flex-col gap-2">
                  {result.relationships.map((relationship, index) => (
                    <div key={index} className={`rounded-lg p-2 text-sm ${cardClass}`}>
                      <span className="font-medium capitalize text-indigo-500">{relationship.type}</span>
                      {relationship.description && <p className={`mt-0.5 text-xs ${textClass}`}>{relationship.description}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!loading && result?.type === "search" && (
          <div className="flex flex-col gap-3">
            {(result.results ?? []).length === 0 && (
              <p className={theme === "dark" ? "text-sm text-gray-500" : "text-sm text-gray-400"}>No relevant passages found.</p>
            )}
            {(result.results ?? []).map((searchResult, index) => (
              <div key={index} className={`rounded-lg p-3 ${cardClass}`}>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <p className="text-xs text-indigo-500">Ch. {searchResult.chapter_num}</p>
                </div>
                <p className={`text-sm leading-relaxed ${textClass}`}>{searchResult.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
