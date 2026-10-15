import { SectionChevron, SurfaceCard } from "./charactersPage.components"
import { formatTraitLabel } from "./charactersPage.helpers"

type TraitEntry = [string, { value: string } | null | undefined]

type CharacterContinuityTabProps = {
  contradictions: string[]
  diagnostics: string[]
  healthIssues: string[]
  isDark: boolean
  traitEntries: TraitEntry[]
}

export function CharacterContinuityTab({
  contradictions,
  diagnostics,
  healthIssues,
  isDark,
  traitEntries,
}: CharacterContinuityTabProps) {
  const checklistItems = [...healthIssues, ...diagnostics]

  return (
    <div className="mt-5 grid gap-4 xl:grid-cols-2">
      <SurfaceCard title="Continuity traits" isDark={isDark}>
        {traitEntries.length > 0 ? (
          <div className="grid gap-3">
            {traitEntries.map(([key, trait]) => trait ? (
              <div key={key} className={`grid grid-cols-[120px_minmax(0,1fr)] gap-3 rounded-sm border px-3 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                <span className={isDark ? "text-slate-400" : "text-stone-600"}>{formatTraitLabel(key)}</span>
                <span className={isDark ? "text-white" : "text-stone-900"}>{trait.value}</span>
              </div>
            ) : null)}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No continuity traits are confirmed yet.</p>
        )}
      </SurfaceCard>

      <SurfaceCard title="Continuity checklist" isDark={isDark}>
        {checklistItems.length ? (
          <div className="space-y-3">
            {checklistItems.map((issue, index) => (
              <div key={`${issue}-${index}`} className={`flex items-start justify-between gap-3 rounded-sm border px-3 py-3 ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                <span>{issue}</span>
                <SectionChevron className={`mt-0.5 h-4 w-4 shrink-0 ${isDark ? "text-slate-400" : "text-stone-600"}`} />
              </div>
            ))}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No hard continuity breaks are tracked yet, but this profile still benefits from a fresh pass on motive drift, scene-to-scene state, and relationship evidence.</p>
        )}
      </SurfaceCard>

      <SurfaceCard title="Contradictions" isDark={isDark} className="xl:col-span-2">
        {contradictions.length > 0 ? (
          <div className="space-y-3">
            {contradictions.map((item, index) => (
              <div key={`${item}-${index}`} className={`rounded-sm border px-4 py-3 text-sm leading-6 ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {item}
              </div>
            ))}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No explicit contradiction is tracked yet, so the next useful check is pressure-testing this character&apos;s role labels, family aliases, and late-chapter motivation shifts.</p>
        )}
      </SurfaceCard>
    </div>
  )
}
