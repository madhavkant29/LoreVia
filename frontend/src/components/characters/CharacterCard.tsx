"use client"
import { useState, type KeyboardEvent } from "react"
import type { Character } from "@/types/character"
import { CONFIDENCE_THRESHOLDS, TRAIT_TYPE_LABELS } from "@/lib/constants"
import { useAuthStore } from "@/lib/stores/authStore"

interface Props { character: Character; compact?: boolean; theme?: "light" | "dark" }

export function CharacterCard({ character, compact = false, theme = "light" }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const user = useAuthStore((state) => state.user)
  const traits = character.trait_state ?? {}
  const visible = Object.entries(traits).filter(
    ([, t]) => t && t.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI
  )
  const isDark = theme === "dark"
  const relationshipSummaries = character.relationship_summaries ?? []
  const isPaid = user?.tier === "pro" || user?.tier === "power" || user?.tier === "admin"
  const advancedTraits = visible.filter(([key]) => !["hair", "eyes", "face", "build", "age", "distinguishing"].includes(key))
  const toggleExpanded = () => setExpanded(v => !v)
  const handleCardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      toggleExpanded()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={toggleExpanded}
      onKeyDown={handleCardKeyDown}
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
          <div className={`rounded-xl border ${isDark ? "border-white/10 bg-white/5" : "border-gray-200 bg-gray-50"}`}>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                setAdvancedOpen((value) => !value)
              }}
              className="flex w-full items-center justify-between px-3 py-2 text-left"
            >
              <div>
                <p className={isDark ? "text-xs font-semibold uppercase tracking-wide text-gray-400" : "text-xs font-semibold uppercase tracking-wide text-gray-500"}>
                  Advanced Details
                </p>
                <p className={isDark ? "text-[11px] text-gray-400" : "text-[11px] text-gray-500"}>
                  {isPaid ? "Expanded unique traits and premium character detail." : "Upgrade to Pro to unlock deeper character detail."}
                </p>
              </div>
              <span className={isDark ? "text-xs text-gray-300" : "text-xs text-gray-600"}>
                {advancedOpen ? "Hide" : isPaid ? "Open" : "Preview"}
              </span>
            </button>
            {advancedOpen ? (
              <div className={`border-t px-3 py-3 ${isDark ? "border-white/10" : "border-gray-200"}`}>
                {isPaid ? (
                  <div className="space-y-2">
                    {character.archetype ? (
                      <div>
                        <p className={isDark ? "text-[11px] font-semibold uppercase tracking-wide text-gray-400" : "text-[11px] font-semibold uppercase tracking-wide text-gray-500"}>Archetype</p>
                        <p className={isDark ? "text-xs text-gray-200 capitalize" : "text-xs text-gray-700 capitalize"}>{character.archetype}</p>
                      </div>
                    ) : null}
                    {character.aliases.length > 0 ? (
                      <div>
                        <p className={isDark ? "text-[11px] font-semibold uppercase tracking-wide text-gray-400" : "text-[11px] font-semibold uppercase tracking-wide text-gray-500"}>Aliases</p>
                        <p className={isDark ? "text-xs text-gray-200" : "text-xs text-gray-700"}>{character.aliases.join(", ")}</p>
                      </div>
                    ) : null}
                    {advancedTraits.length > 0 ? (
                      <div className="space-y-1">
                        <p className={isDark ? "text-[11px] font-semibold uppercase tracking-wide text-gray-400" : "text-[11px] font-semibold uppercase tracking-wide text-gray-500"}>Unique Traits</p>
                        {advancedTraits.map(([key, trait]) => trait ? (
                          <div key={`${character.id}-${key}`} className="flex items-start justify-between gap-3 text-xs">
                            <span className={isDark ? "text-gray-400 capitalize" : "text-gray-500 capitalize"}>{key}</span>
                            <span className={isDark ? "text-gray-100 text-right" : "text-gray-700 text-right"}>{trait.value}</span>
                          </div>
                        ) : null)}
                      </div>
                    ) : (
                      <p className={isDark ? "text-xs text-gray-400" : "text-xs text-gray-500"}>More advanced details will appear as the character profile deepens.</p>
                    )}
                  </div>
                ) : (
                  <p className={isDark ? "text-xs text-gray-300" : "text-xs text-gray-600"}>
                    Premium character detail expands the profile with unique traits, aliases, and richer evolving context.
                  </p>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
