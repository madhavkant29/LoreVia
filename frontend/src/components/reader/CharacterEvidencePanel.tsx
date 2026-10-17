import type { ReactNode } from "react"

import type { SearchResult } from "@/types/reader"

type RelationshipEvidence = {
  counterpartName: string
  description: string | null
  from_chapter?: number | null
  sentiment: number | null
  type: string
}

function EvidenceCard({
  children,
  isDark,
  title,
}: {
  children: ReactNode
  isDark: boolean
  title: string
}) {
  return (
    <section className={`rounded-lg border p-4 ${isDark ? "border-[#17202c] bg-white/[0.025]" : "border-stone-200 bg-stone-50/60"}`}>
      <h3 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</h3>
      <div className="mt-4">{children}</div>
    </section>
  )
}

export function CharacterEvidencePanel({
  characterId,
  characterName,
  error,
  evidence,
  formatRelationshipType,
  isDark,
  loading,
  relationships,
  sentimentLabel,
  onRetry,
}: {
  characterId: string
  characterName: string
  error: string | null
  evidence: SearchResult[]
  formatRelationshipType: (type: string | null | undefined) => string
  isDark: boolean
  loading: boolean
  relationships: RelationshipEvidence[]
  sentimentLabel: (sentiment: number | null | undefined) => string
  onRetry?: () => void
}) {
  return (
    <div className="mt-5 space-y-4">
      <EvidenceCard title="Passage evidence" isDark={isDark}>
        {loading ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>Finding grounded passages...</p> : null}
        {evidence.length > 0 ? (
          <div className="space-y-3">
            {evidence.map((result, index) => (
              <div key={`${characterId}-evidence-${index}`} className={`rounded-md border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                    Chapter {result.chapter_num}
                  </span>
                  {result.chapter_title ? <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{result.chapter_title}</span> : null}
                </div>
                <p className={`mt-2 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.text}</p>
              </div>
            ))}
          </div>
        ) : !loading && !error ? (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No chapter-grounded evidence cards are available yet.</p>
        ) : null}
        {error ? <div role="alert" className={`mt-3 text-sm ${isDark ? "text-rose-300" : "text-rose-700"}`}>
          <p>{error}</p>
          {onRetry ? <button type="button" disabled={loading} onClick={onRetry} className="mt-2 min-h-10 underline underline-offset-4">Retry evidence</button> : null}
        </div> : null}
      </EvidenceCard>

      <EvidenceCard title="Relationship evidence" isDark={isDark}>
        {relationships.length > 0 ? (
          <div className="space-y-3">
            {relationships.map((edge, index) => (
              <div key={`${characterId}-relationship-evidence-${index}`} className={`rounded-md border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{characterName} to {edge.counterpartName}</p>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                  {formatRelationshipType(edge.type)} / {sentimentLabel(edge.sentiment)}{typeof edge.from_chapter === "number" ? ` / Chapter ${edge.from_chapter}` : ""}
                </p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                  {edge.description || "This relationship still needs a grounded description and chapter reference."}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No relationship evidence has been captured yet.</p>
        )}
      </EvidenceCard>
    </div>
  )
}
