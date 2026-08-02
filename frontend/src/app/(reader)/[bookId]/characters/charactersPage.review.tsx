import { candidateAdjudicationBadges } from "@/lib/utils/characterAdjudication"
import type { CharacterCandidate, CharacterRelationshipCandidate } from "@/types/character"
import type { SearchResult } from "@/types/reader"
import { actionButtonClasses, SurfaceCard } from "./charactersPage.components"
import {
  characterInitial,
  formatPercent,
  formatRelationshipType,
  formatResolverStatus,
} from "./charactersPage.helpers"

type ReviewEvidenceCache = Record<string, { chapter: number; results: SearchResult[] }>

type CharacterReviewTabProps = {
  candidateActionId: string | null
  evidenceCache: ReviewEvidenceCache
  filteredPendingCandidatesCount: number
  relationshipCandidates: CharacterRelationshipCandidate[]
  selectedCandidate: CharacterCandidate | null
  hasSelectedCharacter: boolean
  isDark: boolean
  onAttachCandidate: (candidate: CharacterCandidate) => void
  onFindEvidence: (candidate: CharacterCandidate) => void
  onMarkCandidatePlace: (candidate: CharacterCandidate) => void
  onPromoteCandidate: (candidate: CharacterCandidate) => void
  onRejectCandidate: (candidate: CharacterCandidate) => void
}

export function CharacterReviewTab({
  candidateActionId,
  evidenceCache,
  filteredPendingCandidatesCount,
  relationshipCandidates,
  selectedCandidate,
  hasSelectedCharacter,
  isDark,
  onAttachCandidate,
  onFindEvidence,
  onMarkCandidatePlace,
  onPromoteCandidate,
  onRejectCandidate,
}: CharacterReviewTabProps) {
  return (
    <div className="p-5">
      <div className="space-y-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Review queue</p>
            <h2 className={`mt-2 text-3xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Grounded review workspace</h2>
            <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Review held candidates and unresolved relationships with their evidence, resolver reasons, and promotion blockers.
            </p>
          </div>
          {selectedCandidate ? (
            <div className={`rounded-md border px-4 py-3 text-sm ${isDark ? "border-[#202a38] bg-[#0c1119] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
              {`1 of ${Math.max(filteredPendingCandidatesCount, 1)} candidates`}
            </div>
          ) : null}
        </div>

        {selectedCandidate ? (
          <SurfaceCard title="Candidate summary" isDark={isDark}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-2xl font-semibold ${isDark ? "bg-violet-500/18 text-violet-100 ring-1 ring-violet-400/25" : "bg-violet-100 text-violet-700"}`}>
                  {characterInitial(selectedCandidate.proposed_name)}
                </div>
                <div>
                  <h3 className={`text-[1.8rem] font-semibold leading-none ${isDark ? "text-white" : "text-stone-900"}`}>{selectedCandidate.proposed_name}</h3>
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Chapter {selectedCandidate.chapter_number} - {selectedCandidate.confidence}% confidence - {formatResolverStatus(selectedCandidate.resolver_status)}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className={`rounded-sm border px-3 py-2 text-xs ${isDark ? "border-teal-500/20 bg-teal-500/12 text-teal-100" : "border-teal-200 bg-teal-50 text-teal-700"}`}>
                  Grounding {formatPercent(selectedCandidate.grounding_coverage)}
                </span>
                <span className={`rounded-sm border px-3 py-2 text-xs ${isDark ? "border-[#202a38] bg-white/[0.04] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                  Canonical confidence {formatPercent(selectedCandidate.canonical_confidence)}
                </span>
                {candidateAdjudicationBadges(selectedCandidate).map((badge) => (
                  <span key={`${selectedCandidate.id}-${badge}`} className={`rounded-sm border px-3 py-2 text-xs ${isDark ? "border-amber-400/20 bg-amber-400/12 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
                    {badge}
                  </span>
                ))}
              </div>
            </div>

            <div className={`mt-5 grid gap-4 xl:grid-cols-2 ${isDark ? "xl:divide-x xl:divide-[#17202c]" : "xl:divide-x xl:divide-stone-200"}`}>
              <div className="xl:pr-5">
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Resolver reasons</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {((selectedCandidate.resolver_reasons ?? []).length > 0 ? selectedCandidate.resolver_reasons ?? [] : selectedCandidate.reason_codes ?? []).map((reason) => (
                    <span key={reason} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-teal-500/12 text-teal-100" : "bg-teal-50 text-teal-700"}`}>
                      {reason}
                    </span>
                  ))}
                </div>
                <p className={`mt-4 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Cluster names</p>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                  {(selectedCandidate.cluster_names ?? []).length > 0 ? (selectedCandidate.cluster_names ?? []).join(", ") : "No cluster aliases captured yet."}
                </p>
                <p className={`mt-4 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Grounding counts</p>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                  {selectedCandidate.cluster_mention_count ?? 0} mentions across {selectedCandidate.cluster_size ?? 0} clustered names.
                </p>
              </div>
              <div className="xl:pl-5">
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Evidence snippets</p>
                <div className="mt-2 space-y-2">
                  {(selectedCandidate.snippets ?? []).map((snippet, index) => (
                    <div key={`${selectedCandidate.id}-snippet-${index}`} className={`rounded-xl border px-3 py-3 text-sm leading-6 ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                      {snippet}
                    </div>
                  ))}
                  {(selectedCandidate.snippets ?? []).length === 0 ? (
                    <div className={`rounded-xl border px-3 py-3 text-sm leading-6 ${isDark ? "border-[#17202c] bg-black/20 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
                      No evidence snippet is available for this held candidate yet.
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="mt-5 grid gap-2 md:grid-cols-2 xl:grid-cols-5">
              <button type="button" disabled={candidateActionId === selectedCandidate.id || selectedCandidate.status !== "pending"} onClick={() => onPromoteCandidate(selectedCandidate)} className="w-full rounded-md bg-[#1f615d] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">
                {candidateActionId === selectedCandidate.id ? "Promoting..." : "Promote candidate"}
              </button>
              <button type="button" disabled={candidateActionId === selectedCandidate.id || selectedCandidate.status !== "pending" || !hasSelectedCharacter} onClick={() => onAttachCandidate(selectedCandidate)} className={`${actionButtonClasses(isDark)} w-full justify-center`}>
                Attach to selected character
              </button>
              <button type="button" disabled={candidateActionId === selectedCandidate.id} onClick={() => onMarkCandidatePlace(selectedCandidate)} className={`${actionButtonClasses(isDark)} w-full justify-center`}>
                Mark as place
              </button>
              <button type="button" disabled={candidateActionId === selectedCandidate.id} onClick={() => onRejectCandidate(selectedCandidate)} className={`${actionButtonClasses(isDark)} w-full justify-center`}>
                Reject candidate
              </button>
              <button type="button" onClick={() => onFindEvidence(selectedCandidate)} className={`${actionButtonClasses(isDark)} w-full justify-center`}>
                Find evidence
              </button>
            </div>
            {evidenceCache[selectedCandidate.id]?.results?.length ? (
              <div className="mt-4 space-y-2">
                {evidenceCache[selectedCandidate.id].results.slice(0, 3).map((result, index) => (
                  <div key={`${selectedCandidate.id}-search-${index}`} className={`rounded-xl border px-3 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                    <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {result.chapter_num}</p>
                    <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.text}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </SurfaceCard>
        ) : (
          <SurfaceCard title="Queue clear" isDark={isDark}>
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No pending character candidates match the current filters.</p>
          </SurfaceCard>
        )}

        <SurfaceCard title="Relationship review" isDark={isDark}>
          {relationshipCandidates.length > 0 ? (
            <div className="space-y-3">
              {relationshipCandidates.slice(0, 6).map((candidate) => (
                <div key={candidate.id} className={`rounded-xl border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{candidate.raw_character_a} {"<->"} {candidate.raw_character_b}</p>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {candidate.chapter_number}{candidate.rel_type ? ` · ${formatRelationshipType(candidate.rel_type)}` : ""}</p>
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{candidate.description || candidate.reason_codes[0] || "Needs relationship review."}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No unresolved relationship candidates match the current filters.</p>
          )}
        </SurfaceCard>
      </div>
    </div>
  )
}
