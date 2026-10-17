"use client"

import { PanelTitle } from "./PanelTitle"
import { formatNumber, panelClass } from "./utils"

export function ProjectOverviewCard({
  isDark,
  currentWords,
  chapterCount,
  characterCount,
  worldArticleCount,
}: {
  isDark: boolean
  currentWords: number | null
  chapterCount: number | null
  characterCount: number
  worldArticleCount: number
}) {
  const stats = [
    { label: "Total words", value: formatNumber(currentWords) },
    { label: "Chapters", value: formatNumber(chapterCount) },
    { label: "Characters", value: formatNumber(characterCount) },
    { label: "World items", value: formatNumber(worldArticleCount) },
  ]

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Project Overview</PanelTitle>
      <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="min-w-0">
            <p className={`text-xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>{stat.label}</p>
            <p className={`mt-2 text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-slate-950"}`}>{stat.value}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
