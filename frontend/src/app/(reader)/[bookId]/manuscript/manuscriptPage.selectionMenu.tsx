import Link from "next/link"

type ManuscriptSelectionMenuState = { text: string; top: number; left: number } | null

type ManuscriptSelectionMenuProps = {
  bookId: string
  draftSurfaceMode: "edit" | "paged"
  editorMode: "chapter" | "book"
  isDark: boolean
  selectionMenu: ManuscriptSelectionMenuState
  tighteningSelection: boolean
  workspaceTab: string
  onAddCharacterFromSelection: () => void
  onAnnotate: () => void
  onCheckConsistency: () => void
  onTightenSelectedText: () => void
}

export function ManuscriptSelectionMenu({
  bookId,
  draftSurfaceMode,
  editorMode,
  isDark,
  onAddCharacterFromSelection,
  onAnnotate,
  onCheckConsistency,
  onTightenSelectedText,
  selectionMenu,
  tighteningSelection,
  workspaceTab,
}: ManuscriptSelectionMenuProps) {
  if (!selectionMenu || workspaceTab !== "write" || editorMode !== "chapter" || draftSurfaceMode !== "edit") {
    return null
  }

  const neutralButtonClass = `rounded-sm px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/[0.08] text-slate-200" : "bg-stone-100 text-stone-700"}`

  return (
    <div
      className="pointer-events-none fixed z-50 hidden -translate-x-1/2 xl:block"
      style={{ top: selectionMenu.top, left: selectionMenu.left }}
    >
      <div className={`pointer-events-auto flex items-center gap-2 rounded-sm border px-2 py-2 ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`}>
        <button
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onTightenSelectedText()}
          disabled={tighteningSelection}
          className="rounded-sm bg-[#1f615d] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
        >
          {tighteningSelection ? "Tightening..." : "Tighten"}
        </button>
        <button
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={onCheckConsistency}
          className={neutralButtonClass}
        >
          Check consistency
        </button>
        <button
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={onAnnotate}
          className={neutralButtonClass}
        >
          Annotate
        </button>
        <button
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={onAddCharacterFromSelection}
          className={`rounded-sm px-3 py-1.5 text-xs font-medium ${isDark ? "bg-violet-700/30 text-violet-200" : "bg-violet-100 text-violet-800"}`}
        >
          Add as character
        </button>
        <Link
          href={`/${bookId}/advisor`}
          className={neutralButtonClass}
        >
          Ask advisor
        </Link>
      </div>
    </div>
  )
}
