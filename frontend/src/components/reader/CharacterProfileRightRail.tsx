import { memo } from "react"
import type { Character, RelationshipGraph as RelationshipGraphData } from "@/types/character"
import type { SearchResult } from "@/types/reader"
import type { ReactNode } from "react"

export type SidebarTab = "insights" | "evidence"

export type ConnectedRelationship = RelationshipGraphData["edges"][number] & {
  counterpartId: string
  counterpartName: string
}

export type CharacterHealth = {
  score: number
  tone: "strong" | "moderate" | "attention"
  summary: string
  issues: string[]
}

export const CharacterProfileRightRail = memo(function CharacterProfileRightRail({
  character,
  connections,
  evidence,
  evidenceError,
  evidenceLoading,
  health,
  isDark,
  mergeSuggestionCount,
  partitioning,
  selectedTab,
  onFindEvidence,
  onManualMerge,
  onOpenNotes,
  onOpenContinuity,
  onOpenRelationships,
  onPartition,
  onRefreshEvidence,
  onReviewDuplicates,
  onSelectTab,
}: {
  character: Character
  connections: ConnectedRelationship[]
  evidence: SearchResult[]
  evidenceError: string | null
  evidenceLoading: boolean
  health: CharacterHealth
  isDark: boolean
  mergeSuggestionCount: number
  partitioning: boolean
  selectedTab: SidebarTab
  onFindEvidence: () => void
  onManualMerge: () => void
  onOpenNotes: () => void
  onOpenContinuity?: () => void
  onOpenRelationships: () => void
  onPartition: () => void
  onRefreshEvidence: () => void
  onReviewDuplicates: () => void
  onSelectTab: (tab: SidebarTab) => void
}) {
  const continuityItems = [
    ...(character.arc_tracker?.contradictions ?? []),
    ...(character.arc_tracker?.diagnostics ?? []),
    ...health.issues,
  ].slice(0, 3)
  const canonicalConfidence = character.analysis_metadata?.canonical_confidence
  const groundingCoverage = character.analysis_metadata?.grounding_coverage
  const hasCanonicalConfidence = typeof canonicalConfidence === "number" && Number.isFinite(canonicalConfidence)
  const hasGroundingCoverage = typeof groundingCoverage === "number" && Number.isFinite(groundingCoverage)
  const storedMetric = hasCanonicalConfidence ? canonicalConfidence : hasGroundingCoverage ? groundingCoverage : null
  const confidence = storedMetric !== null
    ? Math.max(0, Math.min(100, Math.round(storedMetric <= 1 ? storedMetric * 100 : storedMetric)))
    : health.score
  const confidenceBarClass = hasCanonicalConfidence
    ? confidence >= 80 ? "bg-emerald-600" : confidence >= 55 ? "bg-violet-600" : "bg-amber-500"
    : "bg-violet-600"
  const openQuestions = buildOpenQuestions(character, connections, evidence)
  const revisionNotes = buildRevisionNotes(character, health, mergeSuggestionCount)
  const evidenceBars = buildEvidenceBars(evidence)

  return (
    <div className="p-4">
      <div role="tablist" aria-label="Character insights tabs" className={`flex gap-6 border-b px-1 pb-3 ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
        {([
          ["insights", "Insights"],
          ["evidence", "Evidence"],
        ] as Array<[SidebarTab, string]>).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            id={`character-insights-${value}`}
            aria-controls="character-insights-panel"
            tabIndex={selectedTab === value ? 0 : -1}
            aria-selected={selectedTab === value}
            onClick={() => onSelectTab(value)}
            onKeyDown={(event) => {
              if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return
              event.preventDefault()
              const next = event.key === "Home" ? "insights" : event.key === "End" ? "evidence" : value === "insights" ? "evidence" : "insights"
              onSelectTab(next)
              document.getElementById(`character-insights-${next}`)?.focus()
            }}
            className={`pb-2 text-sm font-medium transition ${sidebarTabClasses(isDark, selectedTab === value)}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div id="character-insights-panel" role="tabpanel" aria-labelledby={`character-insights-${selectedTab}`} tabIndex={0}>
      {selectedTab === "insights" ? (
        <div className="mt-2">
          <SidebarSurface isDark={isDark} title={`Continuity alerts ${continuityItems.length}`}>
            <div className="space-y-3">
              {continuityItems.length > 0 ? continuityItems.map((item, index) => (
                <AlertLine key={`${item}-${index}`} isDark={isDark} tone={index === 0 ? "warning" : "neutral"}>
                  {item}
                </AlertLine>
              )) : (
                <p className={`text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>No character-specific continuity alerts are open.</p>
              )}
              {onOpenContinuity ? <button type="button" onClick={onOpenContinuity} className={linkButtonClasses(isDark)}>View all alerts</button> : null}
            </div>
          </SidebarSurface>

          <SidebarSurface isDark={isDark} title={hasCanonicalConfidence ? "Extraction confidence" : hasGroundingCoverage ? "Grounding coverage" : "Profile coverage"}>
            <div>
              <div className="flex items-baseline justify-between gap-3">
                <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                  {hasCanonicalConfidence
                    ? confidence >= 80 ? "High confidence" : confidence >= 55 ? "Medium confidence" : "Low confidence"
                    : hasGroundingCoverage ? `${confidence}% source-backed` : `${confidence}% recorded`}
                </p>
                <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{confidence}%</span>
              </div>
              <div className={`mt-2 h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
                <div className={`h-full ${confidenceBarClass}`} style={{ width: `${confidence}%` }} />
              </div>
              <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{health.summary}</p>
            </div>
            <button type="button" onClick={onFindEvidence} className={`mt-4 ${linkButtonClasses(isDark)}`}>View details</button>
          </SidebarSurface>

          <SidebarSurface isDark={isDark} title={`Open questions ${openQuestions.length}`}>
            <ul className="space-y-2">
              {openQuestions.map((question) => (
                <li key={question} className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>- {question}</li>
              ))}
            </ul>
            <button type="button" onClick={onOpenNotes} className={`mt-3 ${linkButtonClasses(isDark)}`}>Open character notes</button>
          </SidebarSurface>

          <SidebarSurface isDark={isDark} title={`Revision notes ${revisionNotes.length}`}>
            <div className="space-y-3">
              {revisionNotes.map((note) => (
                <div key={note} className={`border-b pb-3 text-sm leading-6 last:border-b-0 last:pb-0 ${isDark ? "border-[#17202c] text-slate-300" : "border-stone-200 text-stone-600"}`}>
                  {note}
                </div>
              ))}
            </div>
            <button type="button" onClick={onOpenNotes} className={`mt-3 ${linkButtonClasses(isDark)}`}>View all notes</button>
          </SidebarSurface>

          <SidebarSurface isDark={isDark} title="Evidence by chapter">
            {evidenceBars.length > 0 ? (
              <>
                <div className="flex h-24 items-end gap-1">
                  {evidenceBars.map((bar) => (
                    <span key={bar.chapter} className="flex min-w-0 flex-1 items-end" title={`Chapter ${bar.chapter}: ${bar.value}`}>
                      <span className={`w-full rounded-sm ${isDark ? "bg-teal-300/80" : "bg-teal-600/75"}`} style={{ height: `${bar.height}%` }} />
                    </span>
                  ))}
                </div>
                <div className={`mt-2 flex justify-between text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                  <span>{evidenceBars[0].chapter}</span>
                  <span>{evidenceBars[evidenceBars.length - 1].chapter}</span>
                </div>
              </>
            ) : (
              <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No chapter evidence is loaded yet.</p>
            )}
            <button type="button" onClick={onFindEvidence} className={`mt-3 ${linkButtonClasses(isDark)}`}>View all mentions</button>
          </SidebarSurface>

          <SidebarSurface isDark={isDark} title="Quick actions">
            <div className="grid gap-2">
              <ContextRow isDark={isDark} label="Relationships" detail={`${connections.length} connected ties`} action="Open" onClick={onOpenRelationships} />
              <ContextRow isDark={isDark} label="Duplicates" detail={mergeSuggestionCount > 0 ? `${mergeSuggestionCount} suggestions` : "No active suggestions"} action="Review" onClick={onReviewDuplicates} />
              <ContextRow isDark={isDark} label={partitioning ? "Splitting..." : "Split card"} detail="Separate merged identities." action="Split" onClick={onPartition} />
              <ContextRow isDark={isDark} label="Manual merge" detail="Compare another profile." action="Merge" onClick={onManualMerge} />
            </div>
          </SidebarSurface>
        </div>
      ) : (
        <div className="mt-4">
          <SidebarSurface isDark={isDark} title="Evidence">
            <div className="flex items-center justify-between gap-3">
              <p className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{character.name}</p>
              <button type="button" onClick={onRefreshEvidence} className={actionButtonClasses(isDark)}>Refresh</button>
            </div>
            <div className="mt-4 space-y-3">
              {evidenceLoading ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>Searching passages...</p> : null}
              {evidence.slice(0, 5).map((result, index) => (
                <div key={`${character.id}-sidebar-evidence-${index}`} className={`border-b pb-3 last:border-b-0 ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
                  <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Chapter {result.chapter_num}</p>
                  <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.text}</p>
                </div>
              ))}
              {evidence.length === 0 && !evidenceLoading ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No evidence cards are loaded yet.</p> : null}
              {evidenceError ? <p className="text-sm text-rose-400">{evidenceError}</p> : null}
            </div>
          </SidebarSurface>
        </div>
      )}
      </div>
    </div>
  )
})

function buildOpenQuestions(character: Character, connections: ConnectedRelationship[], evidence: SearchResult[]) {
  const questions: string[] = []
  if (!character.goal && !character.arc_tracker?.goal) questions.push(`What does ${character.name} want by the midpoint?`)
  if ((character.motivations ?? []).length === 0) questions.push(`Which scenes best prove ${character.name}'s motivation?`)
  if (connections.length === 0) questions.push(`Who changes ${character.name}'s choices most directly?`)
  if (evidence.length === 0) questions.push(`Which passage should be attached as primary evidence?`)
  if ((character.arc_tracker?.contradictions ?? []).length > 0) questions.push(`Which continuity note should be resolved first?`)
  return questions.slice(0, 3)
}

function buildRevisionNotes(character: Character, health: CharacterHealth, mergeSuggestionCount: number) {
  const notes = [
    character.analysis_metadata?.review_note ?? null,
    ...health.issues.slice(0, 2),
    mergeSuggestionCount > 0 ? `${mergeSuggestionCount} possible duplicate ${mergeSuggestionCount === 1 ? "record needs" : "records need"} review.` : null,
  ].filter((item): item is string => Boolean(item && item.trim()))
  return notes.length > 0 ? notes.slice(0, 3) : ["No revision notes have been attached to this character yet."]
}

function buildEvidenceBars(evidence: SearchResult[]) {
  const buckets = new Map<number, number>()
  for (const item of evidence) {
    buckets.set(item.chapter_num, (buckets.get(item.chapter_num) ?? 0) + 1)
  }
  const chapters = Array.from(buckets.keys()).sort((left, right) => left - right)
  const maxValue = Math.max(...Array.from(buckets.values()), 1)
  return chapters.map((chapter) => {
    const value = buckets.get(chapter) ?? 0
    return { chapter, value, height: Math.round((value / maxValue) * 100) }
  })
}

function AlertLine({ children, isDark, tone }: { children: ReactNode; isDark: boolean; tone: "warning" | "neutral" }) {
  return (
    <div className={`flex gap-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
      <span className={tone === "warning" ? "text-amber-500" : isDark ? "text-slate-400" : "text-stone-600"} aria-hidden="true">!</span>
      <span>{children}</span>
    </div>
  )
}

function linkButtonClasses(isDark: boolean) {
  return `text-xs font-semibold ${isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-700 hover:text-teal-900"}`
}

function SidebarSurface({ children, isDark, title }: { children: ReactNode; isDark: boolean; title: string }) {
  return (
    <section className={`border-b px-1 py-4 last:border-b-0 ${isDark ? "border-[#202a38]" : "border-stone-200"}`}>
      <h3 className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-stone-800"}`}>{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function ContextRow({ action, detail, isDark, label, onClick }: { action: string; detail: string; isDark: boolean; label: string; onClick: () => void }) {
  return (
    <div className={`flex items-center justify-between border-b py-3 last:border-b-0 ${isDark ? "border-[#17202c] text-slate-200" : "border-stone-200 text-stone-700"}`}>
      <div>
        <p className="text-sm font-semibold">{label}</p>
        <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{detail}</p>
      </div>
      <button type="button" onClick={onClick} className={`text-xs font-semibold ${isDark ? "text-slate-300 hover:text-white" : "text-stone-700 hover:text-stone-950"}`}>{action}</button>
    </div>
  )
}

function sidebarTabClasses(isDark: boolean, active: boolean) {
  if (active) return isDark ? "border-b-2 border-teal-300 text-white" : "border-b-2 border-teal-700 text-stone-900"
  return isDark ? "border-b-2 border-transparent text-slate-400 hover:text-slate-200" : "border-b-2 border-transparent text-stone-600 hover:text-stone-800"
}

function actionButtonClasses(isDark: boolean) {
  return `inline-flex items-center rounded-md border px-3 py-2 text-xs font-semibold transition ${isDark ? "border-[#202a38] bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`
}
