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
      <div className="flex items-center justify-between">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Workspace</p>
          <p className={`mt-1 text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{bookTitle || "Current project"}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={onCreateChapter} className={`rounded-md px-3 py-1.5 text-xs ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
            New chapter
          </button>
          <button onClick={onCreateScene} className={`rounded-md px-3 py-1.5 text-xs ${isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>
            New scene
          </button>
        </div>
      </div>
      <div className={`mt-4 rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white"}`}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Manuscript</p>
        <h2 className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{bookTitle}</h2>
        <p className={`mt-2 text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>Story manuscript</p>
        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{fullBookWordCount.toLocaleString()} words across the working draft / {fullBookReadingTime}</p>
      </div>
    </>
  )
}
