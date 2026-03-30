"use client"
import { useState } from "react"
import type { Character } from "@/types/character"
import { CONFIDENCE_THRESHOLDS, TRAIT_TYPE_LABELS } from "@/lib/constants"

interface Props { character: Character; compact?: boolean; theme?: "light" | "dark" }

export function CharacterCard({ character, compact = false, theme = "light" }: Props) {
  const [expanded, setExpanded] = useState(false)
  const traits = character.trait_state ?? {}
  const visible = Object.entries(traits).filter(
    ([, t]) => t && t.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI
  )
  const isDark = theme === "dark"
  const relationshipSummaries = character.relationship_summaries ?? []

  return (
    <button
      type="button"
      onClick={() => setExpanded(v => !v)}
      className={`w-full text-left rounded-xl border p-4 ${compact ? "" : "transition-shadow"} ${
      isDark ? "bg-white/5 border-white/10 text-white" : "bg-white border-gray-200"
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold text-sm shrink-0">
          {character.name[0]}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className={isDark ? "font-semibold text-sm text-white" : "font-semibold text-sm text-gray-900"}>{character.name}</h3>
          {character.role && <p className="text-xs text-indigo-600 capitalize">{character.role}</p>}
        </div>
        {!compact && (
          <span className={isDark ? "text-xs text-gray-400" : "text-xs text-gray-500"}>
            {expanded ? "Hide" : "Expand"}
          </span>
        )}
      </div>
      {character.personality_tags && character.personality_tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {character.personality_tags.slice(0, 3).map(tag => (
            <span key={tag} className={`text-xs px-1.5 py-0.5 rounded capitalize ${isDark ? "bg-white/10 text-gray-200" : "bg-gray-100 text-gray-600"}`}>{tag}</span>
          ))}
        </div>
      )}
      {!compact && character.description && (
        <p className={`text-xs mb-2 ${isDark ? "text-gray-300" : "text-gray-600"}`}>{character.description}</p>
      )}
      {!compact && (
        <div className="flex flex-col gap-0.5">
          {visible.slice(0, 4).map(([key, trait]) => trait && (
            <div key={key} className="grid grid-cols-[78px_minmax(0,1fr)] gap-x-2 gap-y-1 items-start text-xs py-0.5">
              <span className={isDark ? "text-gray-400 capitalize" : "text-gray-400 capitalize"}>{key}:</span>
              <span className={isDark ? "text-gray-100 font-medium min-w-0 break-words" : "text-gray-700 font-medium min-w-0 break-words"}>{trait.value}</span>
              <span className="col-start-2">
                <span className={`inline-flex text-[10px] px-1.5 py-0.5 rounded ${
                trait.confidence >= 0.7 ? "bg-green-50 text-green-600" :
                trait.confidence >= 0.45 ? "bg-amber-50 text-amber-600" :
                "bg-gray-50 text-gray-400"
              }`}>
                {TRAIT_TYPE_LABELS[trait.type]} {Math.round(trait.confidence * 100)}%
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
      {!compact && visible.length === 0 && (
        <p className="text-xs text-gray-400 italic">Appearance details emerging...</p>
      )}
      {!compact && expanded && (
        <div className="mt-3 pt-3 border-t border-black/10 dark:border-white/10 flex flex-col gap-3">
          {relationshipSummaries.length > 0 && (
            <div>
              <p className={isDark ? "text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1" : "text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1"}>Relationships</p>
              <div className="flex flex-col gap-1">
                {relationshipSummaries.map((summary, index) => (
                  <p key={`${character.id}-rel-${index}`} className={isDark ? "text-xs text-gray-200" : "text-xs text-gray-700"}>{summary}</p>
                ))}
              </div>
            </div>
          )}
          {character.motivations.length > 0 && (
            <div>
              <p className={isDark ? "text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1" : "text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1"}>Motivations</p>
              <p className={isDark ? "text-xs text-gray-200" : "text-xs text-gray-700"}>{character.motivations.join(", ")}</p>
            </div>
          )}
          {character.fears.length > 0 && (
            <div>
              <p className={isDark ? "text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1" : "text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1"}>Fears</p>
              <p className={isDark ? "text-xs text-gray-200" : "text-xs text-gray-700"}>{character.fears.join(", ")}</p>
            </div>
          )}
          {character.arc_summary && (
            <div>
              <p className={isDark ? "text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1" : "text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1"}>Arc</p>
              <p className={isDark ? "text-xs text-gray-200" : "text-xs text-gray-700"}>{character.arc_summary}</p>
            </div>
          )}
        </div>
      )}
    </button>
  )
}
