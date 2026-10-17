export function ManuscriptWorkspaceSidebarHeader({
  bookTitle,
  fullBookReadingTime,
  fullBookWordCount,
  isDark,
  onCreateChapter,
  onCreateScene,
}: {
  bookTitle?: string | null
  fullBookReadingTime: string
  fullBookWordCount: number
  isDark: boolean
  onCreateChapter: () => void
  onCreateScene: () => void
}) {
  return (
    <>
      <div>
        <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-300" : "text-stone-600"}`}>Workspace</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button onClick={onCreateChapter} className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-sm border px-3 text-sm font-medium ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
            <span aria-hidden>+</span>
            New chapter
          </button>
          <button onClick={onCreateScene} className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-sm border px-3 text-sm font-medium ${isDark ? "border-emerald-400/25 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/15" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
            <span aria-hidden>+</span>
            New scene
          </button>
        </div>
      </div>
      <div className={`mt-4 rounded-sm border p-4 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white"}`}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-300" : "text-stone-600"}`}>Manuscript</p>
        <h2 className={`mt-3 font-serif text-2xl leading-tight ${isDark ? "text-white" : "text-stone-950"}`}>{bookTitle}</h2>
        <p className={`mt-2 text-sm font-medium ${isDark ? "text-teal-300" : "text-teal-700"}`}>Story manuscript</p>
        <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-500"}`}>{fullBookWordCount.toLocaleString()} words across the working draft</p>
        <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-500"}`}>{fullBookReadingTime}</p>
      </div>
    </>
  )
}
