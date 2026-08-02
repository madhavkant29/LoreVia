import type { ManuscriptAnnotation } from "@/types/book"

import { InlineLoadingRows } from "./manuscriptPage.loading"
import {
  annotationCategoryLabel,
  type buildManuscriptInspectorClasses,
} from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>

type ManuscriptAnnotationListProps = {
  activeAnnotationId: string | null
  annotationActionId: string | null
  annotations: ManuscriptAnnotation[]
  annotationsLoading: boolean
  inspectorClasses: InspectorClasses
  isDark: boolean
  onJumpToAnnotation: (annotation: ManuscriptAnnotation) => void
  onRemoveAnnotation: (annotationId: string) => void
  onUpdateAnnotationStatus: (annotation: ManuscriptAnnotation, status: "open" | "resolved") => void
}

export function ManuscriptAnnotationList({
  activeAnnotationId,
  annotationActionId,
  annotations,
  annotationsLoading,
  inspectorClasses,
  isDark,
  onJumpToAnnotation,
  onRemoveAnnotation,
  onUpdateAnnotationStatus,
}: ManuscriptAnnotationListProps) {
  return (
    <div className={inspectorClasses.section}>
      <p className={inspectorClasses.label}>Chapter annotations</p>
      <div className="mt-3 space-y-2">
        {annotationsLoading ? <InlineLoadingRows label="Loading annotations" isDark={isDark} rows={3} /> : null}
        {!annotationsLoading && annotations.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No annotations saved for this chapter yet.</p> : null}
        {annotations.map((annotation) => (
          <div
            key={annotation.id}
            className={`rounded-md border px-3 py-3 ${activeAnnotationId === annotation.id ? isDark ? "border-amber-400/40 bg-amber-500/10" : "border-amber-300 bg-amber-50" : isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{annotationCategoryLabel(annotation.category)}</p>
                  <span className={`rounded-sm border px-2 py-0.5 text-3xs font-semibold uppercase tracking-[0.14em] ${annotation.status === "resolved" ? isDark ? "border-white/[0.08] bg-white/[0.05] text-slate-300" : "border-stone-200 bg-stone-100 text-stone-700" : isDark ? "border-teal-400/20 bg-teal-500/10 text-teal-200" : "border-teal-200 bg-teal-50 text-teal-800"}`}>
                    {annotation.status}
                  </span>
                  <span className={`${inspectorClasses.chip} uppercase tracking-[0.14em]`}>
                    {annotation.visibility}
                  </span>
                </div>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{annotation.created_by_label} · {new Date(annotation.updated_at).toLocaleString()}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => onJumpToAnnotation(annotation)} className={`text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-600"}`}>Jump</button>
                {annotation.can_edit ? (
                  <button
                    onClick={() => onUpdateAnnotationStatus(annotation, annotation.status === "resolved" ? "open" : "resolved")}
                    disabled={annotationActionId === annotation.id}
                    className={`text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-600"}`}
                  >
                    {annotation.status === "resolved" ? "Reopen" : "Resolve"}
                  </button>
                ) : null}
                {annotation.can_edit ? (
                  <button
                    onClick={() => onRemoveAnnotation(annotation.id)}
                    disabled={annotationActionId === annotation.id}
                    className={inspectorClasses.dangerButton}
                  >
                    Delete
                  </button>
                ) : null}
              </div>
            </div>
            <blockquote className={`mt-3 border-l-2 pl-3 text-sm italic ${isDark ? "border-amber-300/40 text-slate-300" : "border-amber-300 text-stone-600"}`}>
              {annotation.quote}
            </blockquote>
            <p className={`mt-3 whitespace-pre-wrap text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{annotation.comment}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
