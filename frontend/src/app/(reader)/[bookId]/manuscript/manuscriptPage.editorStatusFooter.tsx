import type { BookDraftMap } from "./manuscriptPage.helpers"

type ManuscriptEditorStatusFooterProps = {
  bookDrafts: BookDraftMap
  draftSurfaceMode: "edit" | "paged"
  editorMode: "chapter" | "book"
  isDark: boolean
  saving: boolean
  onSaveFullBook: () => void
}

export function ManuscriptEditorStatusFooter({
  bookDrafts,
  draftSurfaceMode,
  editorMode,
  isDark,
  saving,
  onSaveFullBook,
}: ManuscriptEditorStatusFooterProps) {
  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
      <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
        {draftSurfaceMode === "paged"
          ? "Paged preview is read-only. Switch back to Draft mode to edit text, tighten selections, or anchor annotations."
          : editorMode === "chapter"
          ? "Save runs continuity review and refreshes unresolved plot-thread context immediately after ingest."
          : "Full-book mode lets continuity findings and search hits jump straight to the right chapter card."}
      </p>
      {editorMode === "book" ? (
        <button
          onClick={onSaveFullBook}
          disabled={saving || Object.values(bookDrafts).every((draft) => !draft.text.trim())}
          className={`rounded-sm border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-100 disabled:opacity-40" : "border-stone-200 bg-white text-stone-700 disabled:opacity-40"}`}
        >
          {saving ? "Saving..." : "Save all chapters"}
        </button>
      ) : null}
    </div>
  )
}
