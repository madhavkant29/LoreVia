export function VaultNotesSelectionMenu({
  isDark,
  menu,
  onAddCharacter,
}: {
  isDark: boolean
  menu: { top: number; left: number } | null
  onAddCharacter: () => void
}) {
  if (!menu) return null

  return (
    <div
      className="pointer-events-none fixed z-50 hidden -translate-x-1/2 xl:block"
      style={{ top: menu.top, left: menu.left }}
    >
      <div className={`pointer-events-auto flex items-center gap-2 rounded-full border px-2 py-2 ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`} data-notes-add-character>
        <button
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={onAddCharacter}
          className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-violet-700/30 text-violet-200" : "bg-violet-100 text-violet-800"}`}
        >
          Add as character
        </button>
      </div>
    </div>
  )
}
