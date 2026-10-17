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
        <div className={`mt-4 flex items-center justify-between border-y py-2 text-sm ${isDark ? "border-[#202a38] text-slate-300" : "border-stone-200 text-stone-600"}`}>
          <span>{evidenceCount ? `${evidenceCount} loaded passages` : "No passages loaded"}</span>
          <button type="button" onClick={onOpenEvidence} className={`text-xs font-semibold ${isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-700 hover:text-teal-900"}`}>
            View evidence
          </button>
        </div>
      </SurfaceCard>

      <SurfaceCard title="Identity" isDark={isDark}>
        <dl className="grid gap-4 text-sm">
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Role</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{formatRole(character.role)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Aliases</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{character.aliases.length > 0 ? character.aliases.join(", ") : "None recorded"}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Alias records</dt>
            <dd className="space-y-2">
              {aliasGroups.length > 0 ? aliasGroups.map(([kind, aliases]) => (
                <div key={kind} className={`border-b pb-2 last:border-b-0 ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
                  <p className={`text-xs font-medium capitalize ${isDark ? "text-slate-400" : "text-stone-600"}`}>{kind.replaceAll("_", " ")}</p>
                  <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                    {aliases.map((alias) => `${alias.alias_text} (${Math.round((alias.confidence ?? 0) * 100)}%, ${alias.source})`).join(", ")}
                  </p>
                </div>
              )) : (
                <span className={isDark ? "text-slate-400" : "text-stone-600"}>No structured alias records yet.</span>
              )}
            </dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>First appearance</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterAppearanceText(character.first_chapter)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Last appearance</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterAppearanceText(character.last_seen_chapter ?? character.first_chapter)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Chapter count</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{chapterSpanCount(character)} / {bookCoverageLabel(character, totalChapters)}</dd>
          </div>
          <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
            <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Status</dt>
            <dd className={isDark ? "text-white" : "text-stone-900"}>{reviewStatus}</dd>
          </div>
        </dl>
      </SurfaceCard>

      <SurfaceCard title="Traits and motivations" isDark={isDark}>
        <div className="space-y-4">
          <div>
            <p className={`text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-600"}`}>Traits</p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
              {[
                ...traitEntries.flatMap(([key, trait]) => trait ? [`${formatTraitLabel(key)}: ${trait.value}`] : []),
                ...(character.personality_tags ?? []),
              ].join(", ") || "Traits not recorded"}
            </p>
          </div>
          <div>
            <p className={`text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-600"}`}>Motivations</p>
            {(character.motivations?.length ?? 0) > 0 ? (
              <ul className={`mt-2 space-y-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
                {character.motivations.map((motivation) => <li key={motivation}>- {motivation}</li>)}
              </ul>
            ) : (
              <p className={isDark ? "mt-2 text-sm text-slate-400" : "mt-2 text-sm text-stone-600"}>Motivations not recorded</p>
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
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>Durable facts not recorded</p>
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
          <dl className="grid gap-3 sm:grid-cols-3">
            <div>
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Created</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{character.created_at ? new Date(character.created_at).toLocaleDateString() : "Not recorded"}</dd>
            </div>
            <div>
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Last updated</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{character.approval_updated_at ? new Date(character.approval_updated_at).toLocaleDateString() : "Not tracked"}</dd>
            </div>
            <div>
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Status</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{reviewStatus}</dd>
            </div>
          </dl>
        </div>
      </SurfaceCard>
    </>
  )
}
