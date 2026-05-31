"use client"

type ReadingProgressRailProps = {
  theme: "light" | "dark"
  progressPercent: number | null
  wordsRead: number
  totalWords: number
}

export function ReadingProgressRail({
  theme,
  progressPercent,
  wordsRead,
  totalWords,
}: ReadingProgressRailProps) {
  const railFill = progressPercent !== null ? `${Math.max(0, Math.min(100, progressPercent))}%` : "0%"

  return (
    <aside className="reader-nonprint hidden xl:block">
      <div className="sticky top-28 flex justify-end">
        <div className={`flex min-h-[500px] w-[76px] flex-col items-center rounded-lg border px-3 py-5 ${theme === "dark"
            ? "border-white/10 bg-[#0d1422]/66 text-slate-300 shadow-[0_24px_70px_-56px_rgba(8,15,31,0.9)]"
            : "border-stone-200/80 bg-white/80 text-stone-600"
          }`}>
          <div className="text-center">
            <p className={`text-2xl font-semibold ${theme === "dark" ? "text-white" : "text-stone-950"}`}>
              {progressPercent ?? "–"}%
            </p>
            <p className={`mt-1 text-3xs uppercase tracking-[0.24em] ${theme === "dark" ? "text-slate-500" : "text-stone-400"}`}>
              Of chapter
            </p>
          </div>
          <div className={`my-6 flex flex-1 items-center ${theme === "dark" ? "text-slate-600" : "text-stone-300"}`}>
            <div className="relative h-full w-[4px] rounded-full bg-current/30">
              <div
                className={`absolute bottom-0 left-1/2 w-[4px] -translate-x-1/2 rounded-full ${theme === "dark" ? "bg-gradient-to-t from-[#6d72f6] to-[#a7a9ff]" : "bg-gradient-to-t from-violet-500 to-teal-400"}`}
                style={{ height: railFill }}
              />
              <div
                className={`absolute left-1/2 h-4 w-4 -translate-x-1/2 rounded-full border ${theme === "dark" ? "border-[#a3a7ff] bg-[#a3a7ff]" : "border-violet-400 bg-violet-400"}`}
                style={{ bottom: `calc(${railFill} - 7px)` }}
              />
            </div>
          </div>
          <div className="text-center">
            <p className={`text-sm font-medium ${theme === "dark" ? "text-slate-200" : "text-stone-800"}`}>
              {wordsRead.toLocaleString()}
            </p>
            <p className={`mt-1 text-3xs uppercase tracking-[0.24em] ${theme === "dark" ? "text-slate-500" : "text-stone-400"}`}>
              of {totalWords.toLocaleString()} words
            </p>
          </div>
        </div>
      </div>
    </aside>
  )
}
