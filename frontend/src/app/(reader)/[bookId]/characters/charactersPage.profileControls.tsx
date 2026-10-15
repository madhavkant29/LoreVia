import type { Character, RelationshipGraph as RelationshipGraphData } from "@/types/character"
import { actionButtonClasses, SurfaceCard } from "./charactersPage.components"
import {
  type EditDraft,
  formatPercent,
  formatResolverStatus,
  graphVisibilityLabel,
  graphVisibilityReasonCopy,
  isProtectedCharacter,
} from "./charactersPage.helpers"

type HiddenGraphNode = NonNullable<RelationshipGraphData["hidden_nodes"]>[number]

type CharacterGraphVisibilityCardProps = {
  character: Character
  graphOverrideBusy: boolean
  hiddenGraphRecord: HiddenGraphNode | null
  isAuthorMode: boolean
  isDark: boolean
  onGraphVisibilityOverride: (value: "include" | "exclude" | null) => void
}

export function CharacterGraphVisibilityCard({
  character,
  graphOverrideBusy,
  hiddenGraphRecord,
  isAuthorMode,
  isDark,
  onGraphVisibilityOverride,
}: CharacterGraphVisibilityCardProps) {
  return (
    <SurfaceCard title="Graph visibility" isDark={isDark}>
      <div className="space-y-3">
        <div className={`rounded-sm border px-3 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
          <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{graphVisibilityLabel(character.graph_visibility_override ?? null)}</p>
          <p className="mt-1">
            {hiddenGraphRecord
              ? `${character.name} is currently hidden from the graph.`
              : "Automatic visibility uses profile evidence and relationship signals; a manual override takes priority."}
          </p>
          {hiddenGraphRecord ? (
            <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
              Score {hiddenGraphRecord.visibility_score}. {hiddenGraphRecord.connected_relationship_count} relationship signals.
            </p>
          ) : null}
        </div>
        {hiddenGraphRecord?.visibility_reasons?.length ? (
          <div className="flex flex-wrap gap-2">
            {hiddenGraphRecord.visibility_reasons.map((reason) => (
              <span key={reason} className={`rounded-sm px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>
                {graphVisibilityReasonCopy(reason)}
              </span>
            ))}
          </div>
        ) : null}
        {isAuthorMode ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" aria-pressed={character.graph_visibility_override === "include"} disabled={graphOverrideBusy} onClick={() => onGraphVisibilityOverride("include")} className="rounded-md bg-[#1f615d] px-4 py-2 text-xs font-semibold text-white disabled:opacity-60">
              Include in graph
            </button>
            <button type="button" aria-pressed={character.graph_visibility_override === "exclude"} disabled={graphOverrideBusy} onClick={() => onGraphVisibilityOverride("exclude")} className={`rounded-sm px-4 py-2 text-xs font-semibold disabled:opacity-60 ${isDark ? "border border-[#202a38] text-slate-200 hover:bg-white/[0.05]" : "border border-stone-200 text-stone-700 hover:bg-white"}`}>
              Exclude from graph
            </button>
            <button type="button" aria-pressed={character.graph_visibility_override == null} disabled={graphOverrideBusy} onClick={() => onGraphVisibilityOverride(null)} className={`rounded-sm px-4 py-2 text-xs font-semibold disabled:opacity-60 ${isDark ? "border border-[#202a38] text-slate-200 hover:bg-white/[0.05]" : "border border-stone-200 text-stone-700 hover:bg-white"}`}>
              Return to auto
            </button>
          </div>
        ) : null}
      </div>
    </SurfaceCard>
  )
}

type CharacterReviewControlsCardProps = {
  character: Character
  isDark: boolean
  reviewNoteBusy: boolean
  reviewNoteDraft: string
  saving: boolean
  onApproveCharacter: () => void
  onDemoteSelectedCharacter: () => void
  onRejectCharacter: () => void
  onReviewNoteChange: (value: string) => void
  onSaveReviewNote: () => void
  onToggleProtectedFromRepair: () => void
}

export function CharacterReviewControlsCard({
  character,
  isDark,
  reviewNoteBusy,
  reviewNoteDraft,
  saving,
  onApproveCharacter,
  onDemoteSelectedCharacter,
  onRejectCharacter,
  onReviewNoteChange,
  onSaveReviewNote,
  onToggleProtectedFromRepair,
}: CharacterReviewControlsCardProps) {
  return (
    <SurfaceCard title="Review controls" isDark={isDark}>
      <div className="space-y-3">
        <div className={`rounded-sm border px-3 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
          <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Canonical confidence {formatPercent(character.analysis_metadata?.canonical_confidence)}</p>
          <p className="mt-1">Grounding coverage {formatPercent(character.analysis_metadata?.grounding_coverage)}. Resolver status: {formatResolverStatus(character.analysis_metadata?.resolver_status)}.</p>
        </div>
        <label className="space-y-1">
          <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`}>Reviewer note</span>
          <textarea
            value={reviewNoteDraft}
            onChange={(event) => onReviewNoteChange(event.target.value)}
            rows={4}
            className={`w-full rounded-sm border px-3 py-2 text-sm ${isDark ? "border-[#202a38] bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={reviewNoteBusy} onClick={onSaveReviewNote} className={actionButtonClasses(isDark)}>
            {reviewNoteBusy ? "Saving..." : "Save review note"}
          </button>
          <button type="button" disabled={reviewNoteBusy} onClick={onToggleProtectedFromRepair} className={actionButtonClasses(isDark)}>
            {isProtectedCharacter(character) ? "Unprotect from repair" : "Protect from repair"}
          </button>
          <button type="button" disabled={saving} onClick={onDemoteSelectedCharacter} className={actionButtonClasses(isDark)}>
            {saving ? "Moving..." : "Demote to review"}
          </button>
          {character.approval_state === "pending_review" ? (
            <>
              <button type="button" disabled={saving} onClick={onApproveCharacter} className="inline-flex items-center rounded-sm border px-4 py-2.5 text-sm font-medium transition border-emerald-600 bg-emerald-700 text-white hover:bg-emerald-800">
                {saving ? "Approving..." : "Approve character"}
              </button>
              <button type="button" disabled={saving} onClick={onRejectCharacter} className="inline-flex items-center rounded-sm border px-4 py-2.5 text-sm font-medium transition border-red-500 bg-red-600 text-white hover:bg-red-700">
                {saving ? "Rejecting..." : "Reject as noise"}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </SurfaceCard>
  )
}

type CharacterEditProfileFormProps = {
  actionError: string | null
  draft: EditDraft
  isDark: boolean
  saving: boolean
  onCancel: () => void
  onDraftChange: (updater: (value: EditDraft) => EditDraft) => void
  onSave: () => void
}

export function CharacterEditProfileForm({
  actionError,
  draft,
  isDark,
  saving,
  onCancel,
  onDraftChange,
  onSave,
}: CharacterEditProfileFormProps) {
  const inputClass = `w-full rounded-sm border px-3 py-2 text-sm ${isDark ? "border-[#202a38] bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`
  const labelClass = `text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-600"}`

  return (
    <SurfaceCard title="Edit profile" isDark={isDark} className="xl:col-span-2">
      <fieldset disabled={saving} className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1">
          <span className={labelClass}>Name</span>
          <input value={draft.name} onChange={(event) => onDraftChange((value) => ({ ...value, name: event.target.value }))} className={inputClass} />
        </label>
        <label className="space-y-1">
          <span className={labelClass}>Aliases</span>
          <input value={draft.aliases} onChange={(event) => onDraftChange((value) => ({ ...value, aliases: event.target.value }))} className={inputClass} />
        </label>
        <label className="space-y-1 md:col-span-2">
          <span className={labelClass}>Description</span>
          <textarea value={draft.description} onChange={(event) => onDraftChange((value) => ({ ...value, description: event.target.value }))} rows={4} className={inputClass} />
        </label>
        <label className="space-y-1">
          <span className={labelClass}>Goal</span>
          <input value={draft.goal} onChange={(event) => onDraftChange((value) => ({ ...value, goal: event.target.value }))} className={inputClass} />
        </label>
        <label className="space-y-1">
          <span className={labelClass}>Arc type</span>
          <input value={draft.arcType} onChange={(event) => onDraftChange((value) => ({ ...value, arcType: event.target.value }))} className={inputClass} />
        </label>
        <label className="space-y-1 md:col-span-2">
          <span className={labelClass}>Lie they believe</span>
          <textarea value={draft.lieTheyBelieve} onChange={(event) => onDraftChange((value) => ({ ...value, lieTheyBelieve: event.target.value }))} rows={2} className={inputClass} />
        </label>
        <label className="space-y-1 md:col-span-2">
          <span className={labelClass}>Wound / backstory</span>
          <textarea value={draft.backstoryWound} onChange={(event) => onDraftChange((value) => ({ ...value, backstoryWound: event.target.value }))} rows={3} className={inputClass} />
        </label>
        <label className="space-y-1 md:col-span-2">
          <span className={labelClass}>Arc summary</span>
          <textarea value={draft.arcSummary} onChange={(event) => onDraftChange((value) => ({ ...value, arcSummary: event.target.value }))} rows={3} className={inputClass} />
        </label>
        <label className="space-y-1">
          <span className={labelClass}>Personality tags</span>
          <input value={draft.personalityTags} onChange={(event) => onDraftChange((value) => ({ ...value, personalityTags: event.target.value }))} className={inputClass} />
        </label>
        <label className="space-y-1">
          <span className={labelClass}>Motivations</span>
          <input value={draft.motivations} onChange={(event) => onDraftChange((value) => ({ ...value, motivations: event.target.value }))} className={inputClass} />
        </label>
        <label className="space-y-1 md:col-span-2">
          <span className={labelClass}>Fears</span>
          <input value={draft.fears} onChange={(event) => onDraftChange((value) => ({ ...value, fears: event.target.value }))} className={inputClass} />
        </label>
      </fieldset>
      {actionError ? <p role="alert" className={`mt-3 text-sm ${isDark ? "text-rose-300" : "text-rose-700"}`}>{actionError}</p> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" disabled={saving || !draft.name.trim()} onClick={onSave} className="rounded-md bg-[#1f615d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
          {saving ? "Saving..." : "Save changes"}
        </button>
        <button
          type="button"
          disabled={saving}
          onClick={onCancel}
          className={`rounded-sm border px-4 py-2.5 text-sm font-medium ${isDark ? "border-[#202a38] text-slate-300 hover:bg-white/[0.05]" : "border-stone-200 text-stone-700 hover:bg-white"}`}
        >
          Cancel
        </button>
      </div>
    </SurfaceCard>
  )
}
