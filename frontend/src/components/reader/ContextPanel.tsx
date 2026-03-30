"use client"
import type { ContextResult } from "@/types/reader"
import { CharacterCard } from "@/components/characters/CharacterCard"

interface Props {
  result: ContextResult
  loading: boolean
  onClose: () => void
  theme: "light" | "dark"
}

export function ContextPanel({ result, loading, onClose, theme }: Props) {
  const shellClass = theme === "dark"
    ? "border-l border-white/10 bg-black text-white"
    : "border-l border-gray-100 bg-white text-black"
  const borderClass = theme === "dark" ? "border-b border-white/10" : "border-b border-gray-100"
  const cardClass = theme === "dark" ? "bg-white/5" : "bg-gray-50"
  const textClass = theme === "dark" ? "text-gray-300" : "text-gray-700"

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
                <p className="text-xs text-indigo-500 mb-1">Ch. {r.chapter_num}</p>
                <p className={`text-sm leading-relaxed ${textClass}`}>{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
