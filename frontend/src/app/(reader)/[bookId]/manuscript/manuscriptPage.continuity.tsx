import Link from "next/link"

import type {
  EditorialContinuityIssue,
  EditorialReview,
} from "@/types/intelligence"

import type { buildManuscriptInspectorClasses } from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>

type ManuscriptContinuityPanelProps = {
  bookId: string
  inspectorClasses: InspectorClasses
  isDark: boolean
  review: EditorialReview | null
  onDownloadContinuityReport: () => void
  onJumpToChapter: (chapterNumber: number) => void
  onSaveContinuityIssueAsNote: (issue: EditorialContinuityIssue) => void
}

export function ManuscriptContinuityPanel({
  bookId,
  inspectorClasses,
  isDark,
  review,
  onDownloadContinuityReport,
  onJumpToChapter,
  onSaveContinuityIssueAsNote,
}: ManuscriptContinuityPanelProps) {
  return (
    <div className={inspectorClasses.section}>
      <div className="flex items-center justify-between gap-3">
        <p className={inspectorClasses.label}>Continuity check</p>
        <Link href={`/${bookId}/reports`} className={inspectorClasses.secondaryButton}>Report history</Link>
      </div>
      {review ? (
        <div className="mt-3 space-y-3">
          <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{review.overall_verdict}</p>
          {review.continuity_issues.length > 0 ? review.continuity_issues.map((issue, index) => (
            <div key={`${issue.title}-${index}`} className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-amber-500/20 bg-amber-500/10 text-slate-200" : "border-amber-200 bg-amber-50 text-stone-700"}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <p className="font-semibold">{issue.title}</p>
                  <p className="mt-1 text-xs leading-5 opacity-80">{issue.description}</p>
                  {issue.suggestion ? <p className="mt-2 text-xs font-medium opacity-90">{issue.suggestion}</p> : null}
                </div>
                <button
                  onClick={() => onSaveContinuityIssueAsNote(issue)}
                  className={`${inspectorClasses.secondaryButton} shrink-0 px-2 py-1 text-3xs`}
                >
                  Save as note
                </button>
              </div>
            </div>
          )) : (
            <p className={`text-sm ${isDark ? "text-teal-300" : "text-teal-700"}`}>No continuity issues found in the latest save.</p>
          )}
          {review.insertion_opportunities.length > 0 ? (
            <div className="space-y-2">
              <p className={inspectorClasses.label}>Insertion opportunities</p>
              {review.insertion_opportunities.map((item, index) => (
                <div key={`${item.title}-${index}`} className={`${inspectorClasses.record} text-sm`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold">{item.title}</p>
                      <p className="mt-1 text-xs opacity-75">Chapter {item.target_chapter}{item.target_chapter_title ? ` - ${item.target_chapter_title}` : ""}</p>
                    </div>
                    <button onClick={() => onJumpToChapter(item.target_chapter)} className={`${inspectorClasses.secondaryButton} px-2 py-1 text-3xs`}>
                      Jump there
                    </button>
                  </div>
                  <p className="mt-2 text-xs leading-5 opacity-80">{item.problem}</p>
                  <p className="mt-2 text-xs font-medium opacity-95">Add: {item.what_to_add}</p>
                  <p className="mt-2 text-xs opacity-80">{item.why_here}</p>
                  {item.anchor_excerpt ? <p className="mt-2 text-xs opacity-70">Anchor: “{item.anchor_excerpt}”</p> : null}
                </div>
              ))}
            </div>
          ) : null}
          <button
            onClick={onDownloadContinuityReport}
            className={inspectorClasses.secondaryButton}
          >
            Download continuity report
          </button>
        </div>
      ) : (
        <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Save a chapter to run checks.</p>
      )}
    </div>
  )
}
