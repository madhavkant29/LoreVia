import type { CharacterIdentityDiagnostics, CharacterRepairPreview } from "@/types/character"
import { actionButtonClasses, SurfaceCard } from "./charactersPage.components"

type CharacterRepairTabProps = {
  identityDiagnostics: CharacterIdentityDiagnostics
  identityUndoActionId: string | null
  isDark: boolean
  repairPreview: CharacterRepairPreview
  repairPreviewFetching: boolean
  reprocessAllowDemote: boolean
  reprocessAllowMerge: boolean
  reprocessBusy: boolean
  characterLabel: (characterId: string) => string
  onApplyRepairPlan: () => void
  onRefreshPreview: () => void
  onRepairRelationships: () => void
  onSetReprocessAllowDemote: (value: boolean) => void
  onSetReprocessAllowMerge: (value: boolean) => void
  onUndoIdentityAction: (actionId: string) => void
}

export function CharacterRepairTab({
  identityDiagnostics,
  identityUndoActionId,
  isDark,
  repairPreview,
  repairPreviewFetching,
  reprocessAllowDemote,
  reprocessAllowMerge,
  reprocessBusy,
  characterLabel,
  onApplyRepairPlan,
  onRefreshPreview,
  onRepairRelationships,
  onSetReprocessAllowDemote,
  onSetReprocessAllowMerge,
  onUndoIdentityAction,
}: CharacterRepairTabProps) {
  return (
    <div className="p-5">
      <div className="space-y-5">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Repair workspace</p>
          <h2 className={`mt-2 text-3xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Book reprocess preview</h2>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Preview safe merges, obvious-noise demotions, and protected skips before reprocessing the Character Bible.
          </p>
        </div>

        <SurfaceCard title="Repair controls" isDark={isDark}>
          <div className="grid gap-3 md:grid-cols-2">
            <label className={`rounded-xl border px-4 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
              <div className="flex items-start gap-3">
                <input type="checkbox" checked={reprocessAllowMerge} onChange={(event) => onSetReprocessAllowMerge(event.target.checked)} />
                <div>
                  <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Allow safe duplicate merges</p>
                  <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>Merge duplicate records that meet safety rules.</p>
                </div>
              </div>
            </label>
            <label className={`rounded-xl border px-4 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
              <div className="flex items-start gap-3">
                <input type="checkbox" checked={reprocessAllowDemote} onChange={(event) => onSetReprocessAllowDemote(event.target.checked)} />
                <div>
                  <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Allow obvious-noise demotions</p>
                  <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>Demote low-value noisy records to preserve signal.</p>
                </div>
              </div>
            </label>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={onRefreshPreview} className={actionButtonClasses(isDark)}>
              {repairPreviewFetching ? "Refreshing..." : "Refresh preview"}
            </button>
            <button type="button" disabled={reprocessBusy} onClick={onApplyRepairPlan} className="rounded-md bg-amber-700 px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">
              {reprocessBusy ? "Applying..." : "Apply repair plan"}
            </button>
            <button type="button" disabled={reprocessBusy} onClick={onRepairRelationships} className="rounded-md bg-amber-700 px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">
              {reprocessBusy ? "Repairing..." : "Repair relationship timelines"}
            </button>
          </div>
        </SurfaceCard>

        <div className="grid gap-4 xl:grid-cols-2">
          <SurfaceCard title="Automatic cleanup summary" isDark={isDark}>
            <div className="grid gap-3 sm:grid-cols-4">
              {[
                ["Merges", repairPreview.auto_merged ?? repairPreview.planned_merges.length],
                ["Aliases", repairPreview.auto_aliases ?? repairPreview.planned_aliases?.length ?? 0],
                ["Suppressed", repairPreview.auto_suppressed ?? repairPreview.planned_suppressions?.length ?? repairPreview.planned_demotions.length],
                ["Blocked", repairPreview.blocked_suggestions ?? repairPreview.blocked_duplicate_suggestions?.length ?? 0],
              ].map(([label, value]) => (
                <div key={String(label)} className={`rounded-xl border px-3 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                  <p className={`text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{label}</p>
                </div>
              ))}
            </div>
            <p className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              {repairPreview.remaining_review_items ?? repairPreview.pending_duplicate_suggestions} review items remain after cleanup.
            </p>
          </SurfaceCard>

          <SurfaceCard title="Identity diagnostics" isDark={isDark}>
            <div className="grid gap-3 sm:grid-cols-2">
              <p className={`rounded-xl border px-3 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>{identityDiagnostics.suppressed_count} suppressed records</p>
              <p className={`rounded-xl border px-3 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>{identityDiagnostics.blocked_duplicate_count} blocked duplicate pairs</p>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(identityDiagnostics.suppression_reasons).slice(0, 6).map(([reason, count]) => (
                <span key={reason} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.06] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                  {reason.replaceAll("_", " ")}: {count}
                </span>
              ))}
              {Object.keys(identityDiagnostics.suppression_reasons).length === 0 ? (
                <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No suppression reasons recorded yet.</span>
              ) : null}
            </div>
            <div className="mt-4 space-y-2">
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Recent auto-actions</p>
              {identityDiagnostics.recent_identity_actions.slice(0, 6).map((action) => (
                <div key={action.id} className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border px-3 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
                  <div className="min-w-0">
                    <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{action.action_type.replaceAll("_", " ")}</p>
                    <p className={`mt-1 truncate text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      {[action.surface_text, action.reason, `${Math.round((action.confidence ?? 0) * 100)}%`].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  {action.reversible ? (
                    <button
                      type="button"
                      disabled={identityUndoActionId === action.id}
                      onClick={() => onUndoIdentityAction(action.id)}
                      className={actionButtonClasses(isDark)}
                    >
                      {identityUndoActionId === action.id ? "Undoing..." : "Undo"}
                    </button>
                  ) : null}
                </div>
              ))}
              {identityDiagnostics.recent_identity_actions.length === 0 ? (
                <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No identity actions recorded yet.</p>
              ) : null}
            </div>
          </SurfaceCard>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <SurfaceCard title="Planned merges" isDark={isDark}>
            <p className={`text-4xl font-semibold leading-none ${isDark ? "text-white" : "text-stone-900"}`}>{repairPreview.planned_merges.length}</p>
            <p className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>Safe merges ready to apply.</p>
            <div className="mt-3 space-y-2">
              {repairPreview.planned_merges.slice(0, 8).map(([primaryId, secondaryId]) => (
                <div key={`${primaryId}:${secondaryId}`} className={`rounded-xl border px-3 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
                  {characterLabel(primaryId)} {"<-"} {characterLabel(secondaryId)}
                </div>
              ))}
              {repairPreview.planned_merges.length === 0 ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No safe merges are planned.</p> : null}
            </div>
          </SurfaceCard>

          <SurfaceCard title="Planned demotions" isDark={isDark}>
            <p className={`text-4xl font-semibold leading-none ${isDark ? "text-white" : "text-stone-900"}`}>{repairPreview.planned_demotions.length}</p>
            <p className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>Obvious-noise records ready for review holdback.</p>
            <div className="mt-3 space-y-2">
              {repairPreview.planned_demotions.slice(0, 8).map((characterId) => (
                <div key={characterId} className={`rounded-xl border px-3 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
                  {characterLabel(characterId)}
                </div>
              ))}
              {repairPreview.planned_demotions.length === 0 ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No demotions are planned.</p> : null}
            </div>
          </SurfaceCard>
        </div>

        <SurfaceCard title="Protected skips and chapter refreshes" isDark={isDark}>
          <div className="grid gap-4 xl:grid-cols-2">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Skipped protected merges</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{repairPreview.skipped_protected_merge_pairs.length} protected merge pairs skipped.</p>
            </div>
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Skipped protected demotions</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{repairPreview.skipped_protected_demotions.length} protected records left untouched.</p>
            </div>
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>First chapter refreshes</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{Object.keys(repairPreview.updated_first_chapters).length} records will refresh first-seen chapter.</p>
            </div>
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Last seen refreshes</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{Object.keys(repairPreview.updated_last_seen_chapters).length} records will refresh latest chapter.</p>
            </div>
          </div>
        </SurfaceCard>
      </div>
    </div>
  )
}
