import type { Character } from "@/types/character"
import { SurfaceCard } from "./charactersPage.components"
import {
  bookCoverageLabel,
  chapterSpanCount,
  formatRole,
  formatTraitLabel,
  groupAliasRecordsByKind,
  visibleTraitEntries,
} from "./charactersPage.helpers"

type CharacterOverviewIdentityCardsProps = {
  character: Character
  chapterAppearanceText: (chapter: number | null | undefined) => string
  evidenceCount: number
  growthEventCount: number
  isDark: boolean
  knownFacts: string[]
  reviewStatus: string
  summary: string
  totalChapters?: number | null
  onOpenEvidence: () => void
}

export function CharacterOverviewIdentityCards({
  character,
  chapterAppearanceText,
  evidenceCount,
  growthEventCount,
  isDark,
  knownFacts,
  reviewStatus,
  summary,
  totalChapters,
  onOpenEvidence,
}: CharacterOverviewIdentityCardsProps) {
  const aliasGroups = groupAliasRecordsByKind(character)
  const traitEntries = visibleTraitEntries(character)

  return (
    <>
      <SurfaceCard title="Profile summary" isDark={isDark}>
        <p className={`text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          {summary || "LoreVia is still building a concise grounded profile from the manuscript."}
        </p>
        <div className={`mt-4 flex items-center justify-between rounded-xl border px-3 py-2 text-sm ${isDark ? "border-[#202a38] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
          <span>Grounded in {evidenceCount > 0 ? evidenceCount : growthEventCount} passages</span>
          <button type="button" onClick={onOpenEvidence} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/[0.06] text-white" : "bg-stone-100 text-stone-800"}`}>
            View evidence
          </button>
        </div>
      </SurfaceCard>

      <SurfaceCard title="Identity" isDark={isDark}>
        <dl className="grid gap-4 text-sm">
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Role</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{formatRole(character.role)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Aliases</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{character.aliases.length > 0 ? character.aliases.join(", ") : "None recorded"}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Alias records</dt>
            <dd className="space-y-2">
              {aliasGroups.length > 0 ? aliasGroups.map(([kind, aliases]) => (
                <div key={kind} className={`rounded-xl border px-3 py-2 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                  <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{kind.replaceAll("_", " ")}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {aliases.map((alias) => (
                      <span key={alias.id} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.06] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                        {alias.alias_text} · {Math.round((alias.confidence ?? 0) * 100)}% · {alias.source}
                      </span>
                    ))}
                  </div>
                </div>
              )) : (
                <span className={isDark ? "text-slate-400" : "text-stone-500"}>No structured alias records yet.</span>
              )}
            </dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-500" : "text-stone-500"}>First appearance</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterAppearanceText(character.first_chapter)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Last appearance</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterAppearanceText(character.last_seen_chapter ?? character.first_chapter)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Chapter count</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterSpanCount(character)} / {bookCoverageLabel(character, totalChapters)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Status</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{reviewStatus}</dd>
          </div>
        </dl>
      </SurfaceCard>

      <SurfaceCard title="Traits and motivations" isDark={isDark}>
        <div className="space-y-4">
          <div>
            <p className={`text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-500"}`}>Traits</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {traitEntries.length > 0 ? traitEntries.map(([key, trait]) => trait ? (
                <span key={key} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.06] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                  {formatTraitLabel(key)}: {trait.value}
                </span>
              ) : null) : null}
              {(character.personality_tags?.length ?? 0) > 0 ? character.personality_tags.map((trait) => (
                <span key={trait} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-teal-500/10 text-teal-100" : "bg-teal-50 text-teal-800"}`}>{trait}</span>
              )) : (
                traitEntries.length === 0 ? <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>Traits not recorded</span> : null
              )}
            </div>
          </div>
          <div>
            <p className={`text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-500"}`}>Motivations</p>
            {(character.motivations?.length ?? 0) > 0 ? (
              <ul className={`mt-2 space-y-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
                {character.motivations.map((motivation) => <li key={motivation}>- {motivation}</li>)}
              </ul>
            ) : (
              <p className={isDark ? "mt-2 text-sm text-slate-400" : "mt-2 text-sm text-stone-500"}>Motivations not recorded</p>
            )}
          </div>
        </div>
      </SurfaceCard>

      <SurfaceCard title="Known facts" isDark={isDark}>
        {knownFacts.length > 0 ? (
          <ul className={`space-y-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
            {knownFacts.map((fact) => <li key={fact}>- {fact}</li>)}
          </ul>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>Durable facts not recorded</p>
        )}
      </SurfaceCard>

      <SurfaceCard title="Notes and audit" isDark={isDark}>
        <div className="space-y-4 text-sm">
          <div>
            <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Notes</p>
            <p className={`mt-1 leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              {character.analysis_metadata?.review_note || character.relationship_summaries?.[0] || "Reviewer note not recorded"}
            </p>
          </div>
          <dl className="grid grid-cols-3 gap-3">
            <div>
              <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Created</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{character.created_at ? new Date(character.created_at).toLocaleDateString() : "Not recorded"}</dd>
            </div>
            <div>
              <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Last updated</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{character.approval_updated_at ? new Date(character.approval_updated_at).toLocaleDateString() : "Not tracked"}</dd>
            </div>
            <div>
              <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Status</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{reviewStatus}</dd>
            </div>
          </dl>
        </div>
      </SurfaceCard>
    </>
  )
}
