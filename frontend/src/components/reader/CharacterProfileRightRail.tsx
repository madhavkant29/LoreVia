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
  onOpenRelationships: () => void
  onPartition: () => void
  onRefreshEvidence: () => void
  onReviewDuplicates: () => void
  onSelectTab: (tab: SidebarTab) => void
}) {
  return (
    <div className="p-4">
      <div role="tablist" aria-label="Character insights tabs" className="flex gap-6 border-b px-1 pb-3">
        {([
          ["insights", "Insights"],
          ["evidence", "Evidence"],
        ] as Array<[SidebarTab, string]>).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={selectedTab === value}
            onClick={() => onSelectTab(value)}
            className={`pb-2 text-sm font-medium transition ${sidebarTabClasses(isDark, selectedTab === value)}`}
          >
            {label}
          </button>
        ))}
      </div>

      {selectedTab === "insights" ? (
        <div className="mt-4 space-y-4">
          <SidebarSurface isDark={isDark} title="Character health">
            <div className="flex items-center gap-4">
              <HealthRing score={health.score} tone={health.tone} isDark={isDark} />
              <div>
                <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                  {health.tone === "strong" ? "Strong" : health.tone === "moderate" ? "Moderate" : "Needs attention"}
                </p>
                <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{health.summary}</p>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {health.issues.map((issue, index) => (
                <div key={`${issue}-${index}`} className={`flex items-center justify-between rounded-md border px-3 py-2.5 ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                  <span className="text-sm">{issue}</span>
                  <span className={isDark ? "text-slate-500" : "text-stone-400"} aria-hidden="true">&gt;</span>
                </div>
              ))}
            </div>
          </SidebarSurface>

          <SidebarSurface isDark={isDark} title="Quick actions">
            <div className="grid gap-3 sm:grid-cols-2">
              <QuickAction title="Find evidence" description="Search scenes and grounded passages." isDark={isDark} onClick={onFindEvidence} />
              <QuickAction title="Open relationships" description="View the full relationship graph." isDark={isDark} onClick={onOpenRelationships} />
              <QuickAction title="Review duplicates" description={mergeSuggestionCount > 0 ? `${mergeSuggestionCount} suggestions ready for review.` : "Start a manual merge when the detector misses a match."} isDark={isDark} onClick={onReviewDuplicates} />
              <QuickAction title="Manual merge" description="Choose another record and merge it yourself." isDark={isDark} onClick={onManualMerge} />
              <QuickAction title={partitioning ? "Splitting..." : "Split card"} description="Break a merged record into separate character cards." isDark={isDark} onClick={onPartition} />
            </div>
          </SidebarSurface>

          <SidebarSurface isDark={isDark} title="Context">
            <div className="space-y-3">
              <ContextRow isDark={isDark} label="Relationships" detail={`${connections.length} connected ties`} action="Open" onClick={onOpenRelationships} />
              <ContextRow isDark={isDark} label="Evidence" detail={`${evidence.length} cards loaded`} action="View" onClick={onFindEvidence} />
              <ContextRow isDark={isDark} label="Related notes" detail={`${character.relationship_summaries?.length ?? 0} linked notes`} action="Open" onClick={onOpenNotes} />
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
              {evidenceLoading ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>Searching passages...</p> : null}
              {evidence.slice(0, 5).map((result, index) => (
                <div key={`${character.id}-sidebar-evidence-${index}`} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                  <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {result.chapter_num}</p>
                  <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.text}</p>
                </div>
              ))}
              {evidence.length === 0 && !evidenceLoading ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No evidence cards are loaded yet.</p> : null}
              {evidenceError ? <p className="text-sm text-rose-400">{evidenceError}</p> : null}
            </div>
          </SidebarSurface>
        </div>
      )}
    </div>
  )
})

function SidebarSurface({ children, isDark, title }: { children: ReactNode; isDark: boolean; title: string }) {
  return (
    <section className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{title}</p>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function QuickAction({ description, isDark, onClick, title }: { description: string; isDark: boolean; onClick: () => void; title: string }) {
  return (
    <button type="button" onClick={onClick} className={`rounded-md border p-3 text-left transition ${isDark ? "border-white/10 bg-[#0d121a] hover:border-white/15 hover:bg-[#131c29]" : "border-stone-200 bg-white hover:bg-stone-50"}`}>
      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</p>
      <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{description}</p>
    </button>
  )
}

function ContextRow({ action, detail, isDark, label, onClick }: { action: string; detail: string; isDark: boolean; label: string; onClick: () => void }) {
  return (
    <div className={`flex items-center justify-between rounded-md border px-3 py-3 ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
      <div>
        <p className="text-sm font-semibold">{label}</p>
        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{detail}</p>
      </div>
      <button type="button" onClick={onClick} className={`text-xs font-semibold ${isDark ? "text-slate-300 hover:text-white" : "text-stone-700 hover:text-stone-950"}`}>{action}</button>
    </div>
  )
}

function HealthRing({ score, tone, isDark }: { score: number; tone: CharacterHealth["tone"]; isDark: boolean }) {
  const accent = tone === "strong" ? "#22c55e" : tone === "moderate" ? "#8b5cf6" : "#f59e0b"

  return (
    <div className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full" style={{ background: `conic-gradient(${accent} ${score}%, ${isDark ? "rgba(255,255,255,0.09)" : "rgba(148,163,184,0.2)"} ${score}% 100%)` }}>
      <div className={`flex h-[74px] w-[74px] items-center justify-center rounded-full text-2xl font-semibold ${isDark ? "bg-[#0d1016] text-white" : "bg-white text-stone-950"}`}>{score}%</div>
    </div>
  )
}

function sidebarTabClasses(isDark: boolean, active: boolean) {
  if (active) return isDark ? "border-b-2 border-teal-300 text-white" : "border-b-2 border-teal-700 text-stone-900"
  return isDark ? "border-b-2 border-transparent text-slate-500 hover:text-slate-200" : "border-b-2 border-transparent text-stone-500 hover:text-stone-800"
}

function actionButtonClasses(isDark: boolean) {
  return `inline-flex items-center rounded-md border px-3 py-2 text-xs font-semibold transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`
}
