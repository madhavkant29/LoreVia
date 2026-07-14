export function VaultNoteEmptyState({ isDark }: { isDark: boolean }) {
  return (
    <div className={`flex min-h-[42rem] items-center justify-center px-6 text-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
      Create or select a note to begin.
    </div>
  )
}
