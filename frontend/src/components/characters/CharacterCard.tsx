"use client"
import type { Character } from "@/types/character"
import { CONFIDENCE_THRESHOLDS, TRAIT_TYPE_LABELS } from "@/lib/constants"

interface Props { character: Character; compact?: boolean }

export function CharacterCard({ character, compact = false }: Props) {
  const traits = character.trait_state ?? {}
  const visible = Object.entries(traits).filter(
    ([, t]) => t && t.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI
  )

  return (
    <div className={`bg-white rounded-xl border border-gray-200 p-4 ${compact ? "" : "hover:shadow-sm transition-shadow"}`}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold text-sm shrink-0">
          {character.name[0]}
        </div>
        <div>
          <h3 className="font-semibold text-sm text-gray-900">{character.name}</h3>
          {character.role && <p className="text-xs text-indigo-600 capitalize">{character.role}</p>}
        </div>
      </div>
      {character.personality_tags && character.personality_tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {character.personality_tags.slice(0, 3).map(tag => (
            <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded capitalize">{tag}</span>
          ))}
        </div>
      )}
      {!compact && (
        <div className="flex flex-col gap-0.5">
          {visible.slice(0, 4).map(([key, trait]) => trait && (
            <div key={key} className="flex items-center gap-1.5 text-xs">
              <span className="text-gray-400 capitalize w-14 shrink-0">{key}:</span>
              <span className="text-gray-700 font-medium">{trait.value}</span>
              <span className={`ml-auto text-[10px] px-1 py-0.5 rounded ${
                trait.confidence >= 0.7 ? "bg-green-50 text-green-600" :
                trait.confidence >= 0.45 ? "bg-amber-50 text-amber-600" :
                "bg-gray-50 text-gray-400"
              }`}>
                {TRAIT_TYPE_LABELS[trait.type]} {Math.round(trait.confidence * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}
      {!compact && visible.length === 0 && (
        <p className="text-xs text-gray-400 italic">Appearance details emerging...</p>
      )}
    </div>
  )
}
