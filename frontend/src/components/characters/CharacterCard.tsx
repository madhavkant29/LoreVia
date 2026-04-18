"use client"
import { useState, type KeyboardEvent } from "react"
import type { Character } from "@/types/character"
import { CONFIDENCE_THRESHOLDS, TRAIT_TYPE_LABELS } from "@/lib/constants"
import { useAuthStore } from "@/lib/stores/authStore"

interface Props { character: Character; compact?: boolean; theme?: "light" | "dark" }

function clampText(text: string, maxChars: number) {
  const cleaned = text.replace(/\s+/g, " ").trim()
  if (!cleaned) return ""
  if (cleaned.length <= maxChars) return cleaned
  const sliced = cleaned.slice(0, maxChars - 1)
  const lastStop = Math.max(sliced.lastIndexOf("."), sliced.lastIndexOf(";"), sliced.lastIndexOf(","))
  const candidate = lastStop > maxChars * 0.6 ? sliced.slice(0, lastStop + 1) : sliced
  return `${candidate.trim()}…`
}

function firstSentence(text: string, fallbackMaxChars: number) {
  const cleaned = text.replace(/\s+/g, " ").trim()
  if (!cleaned) return ""
  const match = cleaned.match(/^(.{20,}?[\.\!\?])\s/)
  return match?.[1] ? match[1].trim() : clampText(cleaned, fallbackMaxChars)
}

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
      className={`w-full text-left rounded-[1.35rem] border p-5 ${compact ? "" : "transition hover:-translate-y-0.5 hover:shadow-[0_24px_80px_-60px_rgba(79,70,229,0.5)]"} ${
      isDark ? "bg-white/[0.05] border-white/10 text-white" : "bg-white/92 border-stone-200/80 text-stone-950"
    }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className={`relative flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-[1.1rem] border shadow-inner ${
            isDark ? "border-white/10 bg-white/10 text-white" : "border-stone-200 bg-[linear-gradient(135deg,#f1ecff,#ffffff)] text-violet-700"
          }`}>
            <div className={`absolute inset-0 ${isDark ? "bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.22),transparent_55%)]" : "bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.16),transparent_55%)]"}`} />
            <span className="relative text-lg font-semibold">{String(character.name?.[0] ?? "?").toUpperCase()}</span>
          </div>
          <div className="min-w-0">
            <h3 className={`truncate font-serif text-2xl leading-none ${isDark ? "text-white" : "text-stone-950"}`}>{character.name}</h3>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"
              }`}>
                {character.role ? character.role : "character"}
              </span>
              {typeof character.first_chapter === "number" ? (
                <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                  isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"
                }`}>
                  first seen · ch. {character.first_chapter}
                </span>
              ) : null}
              {character.aliases?.length ? (
                <span className={`truncate rounded-full px-3 py-1 text-[11px] font-medium ${
                  isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"
                }`}>
                  aka {character.aliases.slice(0, 2).join(", ")}
                  {character.aliases.length > 2 ? " +" : ""}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {!compact ? (
          <span className={isDark ? "text-xs text-slate-400" : "text-xs text-stone-500"}>
            {expanded ? "Collapse" : "Open"}
          </span>
        ) : null}
      </div>

      {character.personality_tags && character.personality_tags.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {character.personality_tags.slice(0, expanded ? 6 : 4).map(tag => (
            <span
              key={tag}
              className={`rounded-full px-3 py-1 text-xs capitalize shadow-sm ${
                isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700 border border-stone-200/70"
              }`}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {!compact ? (
        <div className="mt-4">
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Overview</p>
          <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
            {character.description
              ? (expanded ? clampText(character.description, 520) : firstSentence(character.description, 240))
              : "LoreVia is still building this profile from the text."}
          </p>
        </div>
      ) : null}

      {!compact && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className={`rounded-[1.15rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200/80 bg-stone-50"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Snapshot</p>
            <div className="mt-3 space-y-2 text-sm">
              {visible.slice(0, 5).map(([key, trait]) => trait && (
                <div key={key} className="flex items-start justify-between gap-4">
                  <span className={isDark ? "text-slate-400 capitalize" : "text-stone-500 capitalize"}>{key}</span>
                  <span className={isDark ? "text-slate-100 font-medium text-right" : "text-stone-900 font-medium text-right"}>{trait.value}</span>
                </div>
              ))}
              {visible.length === 0 ? (
                <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>Details emerging…</p>
              ) : null}
            </div>
          </div>

          <div className={`rounded-[1.15rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200/80 bg-stone-50"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Continuity</p>
            <div className="mt-3 space-y-3 text-sm">
              {character.arc_summary ? (
                <div>
                  <p className={isDark ? "text-slate-400" : "text-stone-500"}>Arc</p>
                  <p className={isDark ? "text-slate-100" : "text-stone-900"}>{clampText(character.arc_summary, 160)}</p>
                </div>
              ) : (
                <div>
                  <p className={isDark ? "text-slate-400" : "text-stone-500"}>Arc</p>
                  <p className={isDark ? "text-slate-400" : "text-stone-500"}>Still forming.</p>
                </div>
              )}
              {relationshipSummaries.length > 0 ? (
                <div>
                  <p className={isDark ? "text-slate-400" : "text-stone-500"}>Relationships</p>
                  <p className={isDark ? "text-slate-100" : "text-stone-900"}>{clampText(relationshipSummaries.slice(0, 2).join(" "), 180)}</p>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {!compact && expanded && (
        <div className={`mt-5 border-t pt-5 flex flex-col gap-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          {relationshipSummaries.length > 0 && (
            <div>
              <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 mb-2" : "text-xs font-semibold uppercase tracking-[0.22em] text-stone-400 mb-2"}>Relationships</p>
              <div className="flex flex-col gap-2">
                {relationshipSummaries.map((summary, index) => (
                  <div key={`${character.id}-rel-${index}`} className={`rounded-[1rem] border px-4 py-3 text-sm leading-7 ${
                    isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200/70 bg-white text-stone-700"
                  }`}>
                    {summary}
                  </div>
                ))}
              </div>
            </div>
          )}
          {character.motivations.length > 0 && (
            <div>
              <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 mb-2" : "text-xs font-semibold uppercase tracking-[0.22em] text-stone-400 mb-2"}>Motivations</p>
              <p className={isDark ? "text-sm text-slate-200" : "text-sm text-stone-700"}>{character.motivations.slice(0, 8).join(" · ")}</p>
            </div>
          )}
          {character.fears.length > 0 && (
            <div>
              <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 mb-2" : "text-xs font-semibold uppercase tracking-[0.22em] text-stone-400 mb-2"}>Fears</p>
              <p className={isDark ? "text-sm text-slate-200" : "text-sm text-stone-700"}>{character.fears.slice(0, 8).join(" · ")}</p>
            </div>
          )}
          {character.arc_summary && (
            <div>
              <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 mb-2" : "text-xs font-semibold uppercase tracking-[0.22em] text-stone-400 mb-2"}>Arc</p>
              <p className={isDark ? "text-sm text-slate-200" : "text-sm text-stone-700"}>{character.arc_summary}</p>
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
                <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-xs font-semibold uppercase tracking-[0.22em] text-stone-400"}>
                  Advanced Details
                </p>
                <p className={isDark ? "text-[11px] text-slate-400" : "text-[11px] text-stone-500"}>
                  {isPaid ? "Expanded unique traits and premium character detail." : "Upgrade to Pro to unlock deeper character detail."}
                </p>
              </div>
              <span className={isDark ? "text-xs text-slate-300" : "text-xs text-stone-600"}>
                {advancedOpen ? "Hide" : isPaid ? "Open" : "Preview"}
              </span>
            </button>
            {advancedOpen ? (
              <div className={`border-t px-3 py-3 ${isDark ? "border-white/10" : "border-gray-200"}`}>
                {isPaid ? (
                  <div className="space-y-2">
                    {character.archetype ? (
                      <div>
                        <p className={isDark ? "text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400"}>Archetype</p>
                        <p className={isDark ? "text-xs text-gray-200 capitalize" : "text-xs text-gray-700 capitalize"}>{character.archetype}</p>
                      </div>
                    ) : null}
                    {character.aliases.length > 0 ? (
                      <div>
                        <p className={isDark ? "text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400"}>Aliases</p>
                        <p className={isDark ? "text-xs text-gray-200" : "text-xs text-gray-700"}>{character.aliases.join(", ")}</p>
                      </div>
                    ) : null}
                    {advancedTraits.length > 0 ? (
                      <div className="space-y-1">
                        <p className={isDark ? "text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400"}>Unique Traits</p>
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
