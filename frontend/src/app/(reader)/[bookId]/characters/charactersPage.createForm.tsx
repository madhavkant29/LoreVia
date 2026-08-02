import {
  actionButtonClasses,
  sectionEyebrowClasses,
  SurfaceCard,
} from "./charactersPage.components"
import type { CreateDraft } from "./charactersPage.helpers"

type CharacterCreateFormProps = {
  actionError: string | null
  createBusy: boolean
  createDraft: CreateDraft
  isDark: boolean
  onCancel: () => void
  onCreate: () => void
  onDraftChange: (updater: (value: CreateDraft) => CreateDraft) => void
  onReset: () => void
}

export function CharacterCreateForm({
  actionError,
  createBusy,
  createDraft,
  isDark,
  onCancel,
  onCreate,
  onDraftChange,
  onReset,
}: CharacterCreateFormProps) {
  const inputClass = `w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-[#202a38] bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`
  const labelClass = `text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`

  return (
    <div className="p-5">
      <div>
        <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${sectionEyebrowClasses(isDark, "teal")}`}>Manual profile</p>
        <h2 className={`mt-2 text-3xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>New character</h2>
        <p className={`mt-2 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          Add a character LoreVia did not extract yet. This creates a real backend character record and makes it available across the Character Bible and other author tools.
        </p>
      </div>

      <SurfaceCard title="Manual character" isDark={isDark} className="mt-5">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${sectionEyebrowClasses(isDark, "teal")}`}>Basic information</p>
          </div>
          <label className="space-y-1">
            <span className={labelClass}>Name</span>
            <input value={createDraft.name} onChange={(event) => onDraftChange((value) => ({ ...value, name: event.target.value }))} className={inputClass} />
          </label>
          <label className="space-y-1">
            <span className={labelClass}>Role</span>
            <select value={createDraft.role} onChange={(event) => onDraftChange((value) => ({ ...value, role: event.target.value as CreateDraft["role"] }))} className={inputClass}>
              <option value="">Unclassified</option>
              <option value="mc">Primary character</option>
              <option value="sc">Supporting character</option>
              <option value="background">Minor character</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className={labelClass}>First chapter</span>
            <input value={createDraft.firstChapter} onChange={(event) => onDraftChange((value) => ({ ...value, firstChapter: event.target.value }))} inputMode="numeric" className={inputClass} />
          </label>
          <label className="space-y-1">
            <span className={labelClass}>Aliases</span>
            <input value={createDraft.aliases} onChange={(event) => onDraftChange((value) => ({ ...value, aliases: event.target.value }))} className={inputClass} />
            <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Separate multiple aliases with commas.</span>
          </label>
          <label className="space-y-1 md:col-span-2">
            <span className="flex items-center justify-between gap-3">
              <span className={labelClass}>Description</span>
              <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{createDraft.description.length}/600</span>
            </span>
            <textarea value={createDraft.description} onChange={(event) => onDraftChange((value) => ({ ...value, description: event.target.value }))} rows={4} className={inputClass} />
          </label>
          <div className="mt-2 md:col-span-2">
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${sectionEyebrowClasses(isDark, "teal")}`}>Story context</p>
          </div>
          <label className="space-y-1">
            <span className={labelClass}>Goal</span>
            <input value={createDraft.goal} onChange={(event) => onDraftChange((value) => ({ ...value, goal: event.target.value }))} className={inputClass} />
          </label>
          <label className="space-y-1">
            <span className={labelClass}>Arc type</span>
            <input value={createDraft.arcType} onChange={(event) => onDraftChange((value) => ({ ...value, arcType: event.target.value }))} className={inputClass} />
          </label>
          <label className="space-y-1 md:col-span-2">
            <span className={labelClass}>Lie they believe</span>
            <textarea value={createDraft.lieTheyBelieve} onChange={(event) => onDraftChange((value) => ({ ...value, lieTheyBelieve: event.target.value }))} rows={2} className={inputClass} />
          </label>
          <label className="space-y-1 md:col-span-2">
            <span className={labelClass}>Wound / backstory</span>
            <textarea value={createDraft.backstoryWound} onChange={(event) => onDraftChange((value) => ({ ...value, backstoryWound: event.target.value }))} rows={3} className={inputClass} />
          </label>
          <label className="space-y-1 md:col-span-2">
            <span className={labelClass}>Arc summary</span>
            <textarea value={createDraft.arcSummary} onChange={(event) => onDraftChange((value) => ({ ...value, arcSummary: event.target.value }))} rows={3} className={inputClass} />
          </label>
          <label className="space-y-1">
            <span className={labelClass}>Personality tags</span>
            <input value={createDraft.personalityTags} onChange={(event) => onDraftChange((value) => ({ ...value, personalityTags: event.target.value }))} className={inputClass} />
          </label>
          <label className="space-y-1">
            <span className={labelClass}>Motivations</span>
            <input value={createDraft.motivations} onChange={(event) => onDraftChange((value) => ({ ...value, motivations: event.target.value }))} className={inputClass} />
          </label>
          <label className="space-y-1 md:col-span-2">
            <span className={labelClass}>Fears</span>
            <input value={createDraft.fears} onChange={(event) => onDraftChange((value) => ({ ...value, fears: event.target.value }))} className={inputClass} />
          </label>
        </div>
        {actionError ? <p className="mt-3 text-sm text-rose-400">{actionError}</p> : null}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button type="button" onClick={onReset} className={actionButtonClasses(isDark)}>
            Reset form
          </button>
          <button type="button" onClick={onCancel} className={actionButtonClasses(isDark)}>
            Cancel
          </button>
          <button type="button" disabled={createBusy} onClick={onCreate} className="ml-auto rounded-md bg-[#1f615d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
            {createBusy ? "Creating..." : "Create character"}
          </button>
        </div>
      </SurfaceCard>
    </div>
  )
}
