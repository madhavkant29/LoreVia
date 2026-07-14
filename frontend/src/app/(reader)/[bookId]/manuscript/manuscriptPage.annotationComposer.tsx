import { RecoverableInlineError, SaveStatePill } from "@/components/ui/ResponsivenessStatus"
import {
  MANUSCRIPT_ANNOTATION_CATEGORIES,
  MANUSCRIPT_ANNOTATION_CATEGORY_LABELS,
} from "@/lib/utils/manuscriptAnnotations"
import type { ManuscriptAnnotationCategory, SaveState } from "@/types/book"

import type { buildManuscriptInspectorClasses } from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>
type AnnotationVisibility = "shared" | "private"
type AnnotationAnchor = {
  quote: string
  anchorContextBefore: string | null
  anchorContextAfter: string | null
  startOffset: number
  endOffset: number
}
type AnnotationSaveState = {
  saveState: SaveState
  retry: () => void
}

type ManuscriptAnnotationComposerProps = {
  annotationActionId: string | null
  annotationAnchor: AnnotationAnchor | null
  annotationCategory: ManuscriptAnnotationCategory
  annotationDraft: string
  annotationSave: AnnotationSaveState
  annotationVisibility: AnnotationVisibility
  inspectorClasses: InspectorClasses
  isDark: boolean
  onAnnotationCategoryChange: (category: ManuscriptAnnotationCategory) => void
  onAnnotationDraftChange: (value: string) => void
  onAnnotationVisibilityChange: (visibility: AnnotationVisibility) => void
  onCancelAnnotation: () => void
  onOpenAnnotationComposer: () => void
  onSaveAnnotation: () => void
}

export function ManuscriptAnnotationComposer({
  annotationActionId,
  annotationAnchor,
  annotationCategory,
  annotationDraft,
  annotationSave,
  annotationVisibility,
  inspectorClasses,
  isDark,
  onAnnotationCategoryChange,
  onAnnotationDraftChange,
  onAnnotationVisibilityChange,
  onCancelAnnotation,
  onOpenAnnotationComposer,
  onSaveAnnotation,
}: ManuscriptAnnotationComposerProps) {
  return (
    <div className={inspectorClasses.section}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className={inspectorClasses.label}>Annotations</p>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Anchor comments, private notes, and review categories directly to manuscript passages.</p>
        </div>
        <button
          type="button"
          onClick={onOpenAnnotationComposer}
          className={inspectorClasses.secondaryButton}
        >
          Use selection
        </button>
      </div>
      {annotationAnchor ? (
        <div className={`mt-4 rounded-md border p-3 ${isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-amber-200" : "text-amber-800"}`}>Selected passage</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-100" : "text-stone-700"}`}>{annotationAnchor.quote}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <select
              value={annotationCategory}
              onChange={(event) => onAnnotationCategoryChange(event.target.value as ManuscriptAnnotationCategory)}
              className={`${inspectorClasses.input} px-3 py-2 text-sm`}
            >
              {MANUSCRIPT_ANNOTATION_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {MANUSCRIPT_ANNOTATION_CATEGORY_LABELS[category]}
                </option>
              ))}
            </select>
            <div className={`inline-flex rounded-sm border p-1 ${isDark ? "border-white/[0.08] bg-[#080b0c]" : "border-stone-200 bg-white"}`}>
              <button
                type="button"
                onClick={() => onAnnotationVisibilityChange("shared")}
                className={`rounded-sm border-b-2 px-3 py-1.5 text-xs font-semibold ${annotationVisibility === "shared" ? isDark ? "border-teal-300 bg-white/[0.04] text-white" : "border-teal-600 bg-stone-100 text-stone-950" : isDark ? "border-transparent text-slate-300" : "border-transparent text-stone-600"}`}
              >
                Shared
              </button>
              <button
                type="button"
                onClick={() => onAnnotationVisibilityChange("private")}
                className={`rounded-sm border-b-2 px-3 py-1.5 text-xs font-semibold ${annotationVisibility === "private" ? isDark ? "border-teal-300 bg-white/[0.04] text-white" : "border-teal-600 bg-stone-100 text-stone-950" : isDark ? "border-transparent text-slate-300" : "border-transparent text-stone-600"}`}
              >
                Private
              </button>
            </div>
          </div>
          <textarea
            value={annotationDraft}
            onChange={(event) => onAnnotationDraftChange(event.target.value)}
            rows={4}
            className={`${inspectorClasses.input} mt-3 w-full px-3 py-2 text-sm`}
            aria-label="Inline annotation"
          />
          <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Leave an inline annotation for the selected passage.</p>
          {annotationSave.saveState === "error" || annotationSave.saveState === "offline_draft" ? (
            <RecoverableInlineError
              className="mt-3"
              message={annotationSave.saveState === "offline_draft" ? "Annotation is saved as an offline draft." : "Annotation could not be saved."}
              actionLabel="Retry save"
              onAction={() => void annotationSave.retry()}
            >
              Your draft remains in this browser until it is saved or cleared.
            </RecoverableInlineError>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={onSaveAnnotation}
              disabled={annotationActionId === "new" || annotationSave.saveState === "saving" || annotationSave.saveState === "retrying" || !annotationDraft.trim()}
              className={`${inspectorClasses.primaryButton} px-4 py-2 text-sm`}
            >
              {annotationSave.saveState === "saving" || annotationActionId === "new"
                ? "Saving..."
                : annotationSave.saveState === "retrying"
                  ? "Retrying..."
                  : "Save annotation"}
            </button>
            <SaveStatePill state={annotationSave.saveState} />
            <button
              type="button"
              onClick={onCancelAnnotation}
              className={`${inspectorClasses.secondaryButton} px-4 py-2 text-sm`}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Highlight text in the chapter editor, then add an annotation from the floating menu, toolbar, or Ctrl/Cmd+Shift+M.</p>
      )}
    </div>
  )
}
