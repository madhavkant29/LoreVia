import type { CharacterCandidate, CharacterRepairPreview } from "@/types/character"
import { sectionEyebrowClasses } from "./charactersPage.components"

type CharacterCreateSidePanelProps = {
  isDark: boolean
}

export function CharacterCreateSidePanel({ isDark }: CharacterCreateSidePanelProps) {
  return (
    <div className="p-4">
      <div className="space-y-4">
        <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Manual add</p>
          <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Use this for characters LoreVia missed, off-page characters you still want tracked, or deliberate naming choices you do not want to wait for extraction to infer.
          </p>
        </section>

        <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Tips</p>
          <div className="mt-4 space-y-3 text-sm leading-6">
            <p className={isDark ? "text-slate-300" : "text-stone-600"}>Add a short description if you want the new profile to read well immediately.</p>
            <p className={isDark ? "text-slate-300" : "text-stone-600"}>Set the first chapter to where this character truly enters the story so timeline tools stay grounded.</p>
            <p className={isDark ? "text-slate-300" : "text-stone-600"}>Aliases help duplicate review later if the manuscript uses family-role labels or nicknames.</p>
          </div>
        </section>
      </div>
    </div>
  )
}

type CharacterReviewSidePanelProps = {
  candidateCount: number
  isDark: boolean
  mergeSuggestionCount: number
  relationshipCandidateCount: number
  selectedCandidate: CharacterCandidate | null
}

export function CharacterReviewSidePanel({
  candidateCount,
  isDark,
  mergeSuggestionCount,
  relationshipCandidateCount,
  selectedCandidate,
}: CharacterReviewSidePanelProps) {
  const candidateReasons = selectedCandidate
    ? ((selectedCandidate.resolver_reasons ?? []).length > 0
      ? selectedCandidate.resolver_reasons ?? []
      : selectedCandidate.reason_codes ?? [])
    : []

  return (
    <div className="p-4">
      <div className="space-y-4">
        <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${sectionEyebrowClasses(isDark, "teal")}`}>Review guide</p>
          <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Promote grounded candidates into the cast, attach partial matches to the selected character, or reject role-label noise before it pollutes the bible.
          </p>
        </section>

        {selectedCandidate ? (
          <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Current candidate</p>
            <p className={`mt-3 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{selectedCandidate.proposed_name}</p>
            <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Chapter {selectedCandidate.chapter_number}
              {" \u00b7 "}
              {selectedCandidate.confidence}% confidence
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {candidateReasons.slice(0, 3).map((reason) => (
                <span key={reason} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-teal-500/12 text-teal-100" : "bg-teal-50 text-teal-700"}`}>
                  {reason}
                </span>
              ))}
            </div>
          </section>
        ) : null}

        <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Queue health</p>
          <div className="mt-4 space-y-3">
            <MetricTile isDark={isDark} label="Candidates" value={candidateCount} />
            <MetricTile isDark={isDark} label="Relationship items" value={relationshipCandidateCount} />
            <MetricTile isDark={isDark} label="Merge suggestions" value={mergeSuggestionCount} />
          </div>
        </section>
      </div>
    </div>
  )
}

type CharacterRepairSidePanelProps = {
  isDark: boolean
  repairPreview: CharacterRepairPreview
  reprocessAllowDemote: boolean
  reprocessAllowMerge: boolean
}

export function CharacterRepairSidePanel({
  isDark,
  repairPreview,
  reprocessAllowDemote,
  reprocessAllowMerge,
}: CharacterRepairSidePanelProps) {
  return (
    <div className="p-4">
      <div className="space-y-4">
        <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${sectionEyebrowClasses(isDark, "amber")}`}>Repair guidance</p>
          <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Review the safe plan first. Protected or manually curated records stay out of automated cleanup unless you act on them explicitly elsewhere.
          </p>
        </section>

        <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Preview totals</p>
          <div className="mt-4 grid gap-3">
            <MetricTile isDark={isDark} label="Planned merges" value={repairPreview.planned_merges.length} />
            <MetricTile isDark={isDark} label="Planned demotions" value={repairPreview.planned_demotions.length} />
            <MetricTile isDark={isDark} label="Protected skips" value={repairPreview.skipped_protected_merge_pairs.length + repairPreview.skipped_protected_demotions.length} />
          </div>
        </section>

        <section className={`rounded-md border p-4 ${isDark ? "border-[#202a38] bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Current safeguards</p>
          <div className="mt-4 space-y-2 text-sm leading-6">
            <p className={isDark ? "text-slate-300" : "text-stone-600"}>{reprocessAllowMerge ? "Safe duplicate merges are enabled." : "Safe duplicate merges are paused."}</p>
            <p className={isDark ? "text-slate-300" : "text-stone-600"}>{reprocessAllowDemote ? "Obvious-noise demotions are enabled." : "Obvious-noise demotions are paused."}</p>
          </div>
        </section>
      </div>
    </div>
  )
}

function MetricTile({ isDark, label, value }: { isDark: boolean; label: string; value: number }) {
  return (
    <div className={`rounded-xl border px-3 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
      <p className={`text-xs uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-1 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
    </div>
  )
}
