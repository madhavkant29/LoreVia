import type { ReactNode } from "react"
export const FEEDBACK_KIND_OPTIONS = [
  { value: "chapter_comment", label: "Chapter comment", detail: "General comments on pacing, flow, or impact in a chapter." },
  { value: "scene_reaction", label: "Scene reaction", detail: "Quick emotional or craft reaction to a specific scene." },
  { value: "answer", label: "Answer question", detail: "Respond directly to one of the author's review prompts." },
  { value: "confusing", label: "Confusing part", detail: "Mark a moment that was hard to follow." },
  { value: "boring", label: "Boring part", detail: "Flag a section that dragged or lost momentum." },
  { value: "favorite", label: "Favorite moment", detail: "Capture what landed hardest or felt most memorable." },
] as const
export const FINAL_RATING_OPTIONS = [5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1] as const

export function StatPill({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className={`border-l px-3 py-1 first:border-l-0 first:pl-0 ${isDark ? "border-white/10" : "border-stone-200"}`}>
      <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{label}</p>
      <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{value}</p>
    </div>
  )
}

export function LabeledField({
  label,
  detail,
  isDark,
  children,
}: {
  label: string
  detail?: string
  isDark: boolean
  children: ReactNode
}) {
  return (
    <label className="grid content-start gap-2">
      <span className={`text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>{label}</span>
      {children}
      {detail ? <span className={`text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-500"}`}>{detail}</span> : null}
    </label>
  )
}

