import { ManuscriptVersionHistory } from "@/components/reader/ManuscriptVersionHistory"
import type { ChapterVersion, ChapterVersionDetail } from "@/types/book"

type ManuscriptLeftRailTailProps = {
  bookGoalProgress: number | null
  bookTargetWordCount: number
  chapterVersionDetail: ChapterVersionDetail | null
  chapterVersionNameDraft: string
  chapterVersions: ChapterVersion[]
  currentText: string
  fullBookWordCount: number
  isDark: boolean
  restoringVersionId: string | null
  selectedChapter: number | null
  onCreateSnapshot: () => void
  onPreviewSnapshot: (versionId: string) => void
  onRestoreSnapshot: (versionId: string) => void
  onVersionNameChange: (value: string) => void
}

export function ManuscriptLeftRailTail({
  bookGoalProgress,
  bookTargetWordCount,
  chapterVersionDetail,
  chapterVersionNameDraft,
  chapterVersions,
  currentText,
  fullBookWordCount,
  isDark,
  restoringVersionId,
  selectedChapter,
  onCreateSnapshot,
  onPreviewSnapshot,
  onRestoreSnapshot,
  onVersionNameChange,
}: ManuscriptLeftRailTailProps) {
  return (
    <>
      <div className={`mt-4 rounded-sm border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
        <div className="flex items-center justify-between gap-3">
          <p className={`text-sm font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>Manuscript progress</p>
          <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{bookGoalProgress ?? 0}%</span>
        </div>
        <div className={`mt-3 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-100"}`}>
          <div className="h-full rounded-full bg-[#1f615d]" style={{ width: `${Math.max(12, bookGoalProgress ?? 18)}%` }} />
        </div>
        <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
          {fullBookWordCount.toLocaleString()} / {bookTargetWordCount.toLocaleString()} words
        </p>
      </div>
      {selectedChapter !== null ? (
        <ManuscriptVersionHistory
          chapterNumber={selectedChapter}
          chapterVersionDetail={chapterVersionDetail}
          chapterVersionNameDraft={chapterVersionNameDraft}
          chapterVersions={chapterVersions}
          currentText={currentText}
          isDark={isDark}
          restoringVersionId={restoringVersionId}
          onCreateSnapshot={onCreateSnapshot}
          onPreviewSnapshot={onPreviewSnapshot}
          onRestoreSnapshot={onRestoreSnapshot}
          onVersionNameChange={onVersionNameChange}
        />
      ) : null}
    </>
  )
}
