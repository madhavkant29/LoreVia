import { LastSavedLabel, SaveStatePill } from "@/components/ui/ResponsivenessStatus"
import type { SaveState } from "@/types/book"

type ManuscriptMobileFooterProps = {
  activeChapterNumber: number
  activeLastSavedAt?: string | Date | null
  activeSaveState: SaveState
  chapterTitle: string
  isDark: boolean
  saving: boolean
  onSave: () => void
}

export function ManuscriptMobileFooter({
  activeChapterNumber,
  activeLastSavedAt,
  activeSaveState,
  chapterTitle,
  isDark,
  saving,
  onSave,
}: ManuscriptMobileFooterProps) {
  return (
    <div data-lorevia-bottom-floating className={`fixed inset-x-0 bottom-0 z-40 border-t px-4 py-3 shadow-lg lg:hidden ${isDark ? "border-white/10 bg-[#111416]/95" : "border-stone-200 bg-white/95"}`}>
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-3">
        <div className="min-w-0">
          <p className={`truncate text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-950"}`}>
            {chapterTitle || `Chapter ${activeChapterNumber}`}
          </p>
          <LastSavedLabel value={activeLastSavedAt} />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <SaveStatePill state={activeSaveState} />
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="app-button-primary min-h-11 px-3 text-sm dark:bg-teal-700 dark:text-white"
          >
            {saving ? "Saving..." : activeSaveState === "error" ? "Retry" : "Save"}
          </button>
        </div>
      </div>
    </div>
  )
}
