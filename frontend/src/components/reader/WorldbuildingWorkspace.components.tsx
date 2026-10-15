import { cloneElement, isValidElement, useId, type ReactNode, type ReactElement } from "react"

import { Skeleton } from "@/components/ui/Skeleton"
import type { WorldNote } from "@/types/world-building"

import {
  accentDotClass,
  accentOutlineButtonClass,
  badgeClass,
  bodyTextClass,
  dangerButtonClass,
  eyebrowClass,
  mutedTextClass,
  panelClass,
  secondaryButtonClass,
  softPanelClass,
  titleTextClass,
} from "./WorldbuildingWorkspace.helpers"

export function WorkspaceCard({
  sectionLabel,
  title,
  description,
  action,
  children,
  isDark,
}: {
  number: string
  sectionLabel: string
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
  isDark: boolean
}) {
  return (
    <section className={`min-w-0 border-y py-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
      <div className={`flex flex-col gap-3 border-b pb-4 md:flex-row md:items-start md:justify-between ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <p className={eyebrowClass(isDark)}>{sectionLabel}</p>
          </div>
          <h2 className={`mt-2 text-[1.15rem] font-semibold ${titleTextClass(isDark)}`}>{title}</h2>
          {description ? <p className={`mt-1.5 max-w-3xl text-sm leading-6 ${mutedTextClass(isDark)}`}>{description}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="pt-4">{children}</div>
    </section>
  )
}

export function MetricCard({
  label,
  value,
  note,
  accent,
  isDark,
}: {
  label: string
  value: string
  note: string
  accent: "teal" | "blue" | "violet" | "amber"
  isDark: boolean
}) {
  return (
    <div className={`rounded-lg border px-4 py-4 ${panelClass(isDark)}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={eyebrowClass(isDark)}>{label}</p>
          <p className={`mt-2.5 text-[2rem] font-semibold leading-none ${titleTextClass(isDark)}`}>{value}</p>
          <p className={`mt-2 text-sm ${mutedTextClass(isDark)}`}>{note}</p>
        </div>
        <span className={`mt-1 h-3 w-3 rounded-full ${accentDotClass(accent, isDark)}`} aria-hidden="true" />
      </div>
    </div>
  )
}

export function LabeledField({
  label,
  children,
  isDark,
}: {
  label: string
  children: ReactNode
  isDark: boolean
}) {
  const inputId = useId()
  return (
    <div className="block">
      <label htmlFor={inputId} className={`mb-2 block text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{label}</label>
      {isValidElement(children) ? cloneElement(children as ReactElement<{ id?: string }>, { id: inputId }) : children}
    </div>
  )
}

export function SectionPanel({
  title,
  meta,
  description,
  children,
  isDark,
}: {
  title: string
  meta?: string
  description?: string
  children: ReactNode
  isDark: boolean
}) {
  return (
    <div className={`rounded-lg border p-4 ${isDark ? "border-white/10 bg-[#08101b]" : "border-stone-200 bg-stone-50/80"}`}>
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h3 className={`text-base font-semibold ${titleTextClass(isDark)}`}>{title}</h3>
          {description ? <p className={`mt-1 text-sm ${mutedTextClass(isDark)}`}>{description}</p> : null}
        </div>
        {meta ? <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${mutedTextClass(isDark)}`}>{meta}</p> : null}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  )
}

export function EvidencePanel({ title, body, isDark }: { title: string; body: string; isDark: boolean }) {
  return (
    <div className={`rounded-md border p-3 ${softPanelClass(isDark)}`}>
      <p className={eyebrowClass(isDark)}>{title}</p>
      <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{body}</p>
    </div>
  )
}

export function EmptyState({
  title,
  description,
  isDark,
  action,
  compact = false,
}: {
  title: string
  description: string
  isDark: boolean
  action?: ReactNode
  compact?: boolean
}) {
  return (
    <div className={`rounded-lg border border-dashed px-5 text-center ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-300 bg-stone-50"} ${compact ? "py-6" : "py-10"}`}>
      <p className={`text-sm font-medium ${titleTextClass(isDark)}`}>{title}</p>
      <p className={`mt-2 text-sm ${mutedTextClass(isDark)}`}>{description}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  )
}

export function LoadingState({ label, isDark }: { label: string; isDark: boolean }) {
  return (
    <div className={`rounded-lg border border-dashed px-5 py-6 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-300 bg-stone-50"}`} role="status" aria-label={label} aria-busy="true">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-4 w-52 max-w-full" />
      <Skeleton className="mt-3 h-3 w-full" />
      <Skeleton className="mt-2 h-3 w-4/5" />
    </div>
  )
}

export function BacklogColumn({
  label,
  count,
  emptyTitle,
  items,
  isDark,
}: {
  label: string
  count: number
  emptyTitle: string
  items: ReactNode[]
  isDark: boolean
}) {
  return (
    <div className={`rounded-lg border p-4 ${softPanelClass(isDark)}`}>
      <div className="flex items-center gap-2">
        <p className={eyebrowClass(isDark)}>{label}</p>
        <span className={badgeClass(isDark)}>{count}</span>
      </div>
      <div className="mt-4 space-y-3">
        {items.length === 0 ? <p className={`text-sm ${mutedTextClass(isDark)}`}>{emptyTitle}</p> : items}
      </div>
    </div>
  )
}

export function NoteCard({
  note,
  isDark,
  noteStatusId,
  onPrimaryAction,
  onDelete,
  primaryLabel,
  addressed = false,
}: {
  note: WorldNote
  isDark: boolean
  noteStatusId: string | null
  onPrimaryAction: () => void
  onDelete: () => void
  primaryLabel: string
  addressed?: boolean
}) {
  return (
    <article className={`rounded-md border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h4 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{note.title || "Untitled note"}</h4>
          <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>
            {addressed
              ? `Resolved ${note.addressed_at ? new Date(note.addressed_at).toLocaleDateString() : "recently"}`
              : `${note.context_label || "General world gap"}${note.chapter_number ? ` - Chapter ${note.chapter_number}` : ""}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onPrimaryAction}
            disabled={noteStatusId === note.id}
            className={addressed ? secondaryButtonClass(isDark) : accentOutlineButtonClass("teal", isDark)}
          >
            {primaryLabel}
          </button>
          <button
            type="button"
            onClick={onDelete}
            disabled={noteStatusId === note.id}
            className={dangerButtonClass(isDark)}
          >
            Delete
          </button>
        </div>
      </div>
      <p className={`mt-3 text-sm leading-6 ${bodyTextClass(isDark)}`}>{note.body}</p>
      {note.suggested_fix ? <p className={`mt-3 text-xs leading-6 ${isDark ? "text-amber-100" : "text-amber-900"}`}>Suggested fix: {note.suggested_fix}</p> : null}
    </article>
  )
}
