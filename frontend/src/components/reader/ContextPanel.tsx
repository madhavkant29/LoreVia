"use client"
import type { ContextResult } from "@/types/reader"
import { CharacterCard } from "@/components/characters/CharacterCard"
import { CONFIDENCE_THRESHOLDS } from "@/lib/constants"

interface Props { result: ContextResult; loading: boolean; onClose: () => void }

export function ContextPanel({ result, loading, onClose }: Props) {
  return (
    <aside className="w-80 border-l border-gray-100 bg-white flex flex-col overflow-hidden shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <span className="text-sm font-medium text-gray-700">Context</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg">×</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {loading && <div className="text-center py-8 text-gray-400 text-sm">Loading...</div>}
        {!loading && result.type === "character" && result.character && (
          <div>
            <CharacterCard character={result.character} />
            {result.relationships && result.relationships.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">Relationships</p>
                <div className="flex flex-col gap-2">
                  {result.relationships.map((r, i) => (
                    <div key={i} className="text-sm bg-gray-50 rounded-lg p-2">
                      <span className="capitalize font-medium text-indigo-600">{r.type}</span>
                      {r.description && <p className="text-gray-600 text-xs mt-0.5">{r.description}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {!loading && result.type === "search" && (
          <div className="flex flex-col gap-3">
            {(result.results ?? []).length === 0 && <p className="text-sm text-gray-400">No relevant passages found.</p>}
            {(result.results ?? []).map((r, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-indigo-600 mb-1">Ch. {r.chapter_num}</p>
                <p className="text-sm text-gray-700 leading-relaxed">{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
