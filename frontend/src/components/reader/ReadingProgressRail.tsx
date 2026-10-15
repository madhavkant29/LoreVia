"use client"

import { memo } from "react"

type ReadingProgressRailProps = {
  theme: "light" | "dark"
  progressPercent: number | null
  wordsRead: number
  totalWords: number
}

export const ReadingProgressRail = memo(function ReadingProgressRail({ theme, progressPercent, wordsRead, totalWords }: ReadingProgressRailProps) {
  return (
    <aside aria-label="Reading position" className={`reader-nonprint hidden border-l pl-4 text-sm xl:block ${theme === "dark" ? "border-white/15 text-slate-300" : "border-stone-300 text-stone-700"}`}>
      <p className="font-medium">Position</p>
      <p className={`mt-2 text-xl ${theme === "dark" ? "text-white" : "text-stone-950"}`}>{progressPercent === null ? "—" : `${progressPercent}%`}</p>
      <p className="mt-2 leading-6">Through this chapter</p>
      {totalWords > 0 ? <p className="mt-6 leading-6">{wordsRead.toLocaleString()} of {totalWords.toLocaleString()} words</p> : null}
      <p className="mt-6 leading-6">Your position saves as you scroll.</p>
    </aside>
  )
})