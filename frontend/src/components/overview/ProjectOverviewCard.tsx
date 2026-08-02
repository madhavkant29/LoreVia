"use client"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import type { IconName } from "./types"
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
    { label: "Total words", value: formatNumber(currentWords), icon: "spark" as IconName, color: "text-teal-700", path: "M2 17c2-5 4-2 6-5s4 1 6-3 4 0 6-4" },
    { label: "Chapters", value: formatNumber(chapterCount), icon: "book" as IconName, color: "text-blue-400", path: "M2 15c2-1 3-6 5-4s2 6 5 3 4-6 8-4" },
    { label: "Characters", value: formatNumber(characterCount), icon: "users" as IconName, color: "text-emerald-400", path: "M2 16c3-3 4 1 7-2s5-7 11-5" },
    { label: "World items", value: formatNumber(worldArticleCount), icon: "file" as IconName, color: "text-amber-400", path: "M2 17c4-1 4-8 7-5s3 6 6 2 4-4 5-3" },
  ]

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Project Overview</PanelTitle>
      <div className="mt-6 grid gap-4 sm:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="min-w-0">
            <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{stat.label}</p>
            <p className={`mt-2 text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-slate-950"}`}>{stat.value}</p>
            <div className="mt-5 flex items-end gap-2">
              <Icon name={stat.icon} className={`h-5 w-5 ${stat.color}`} />
              <svg className={`h-8 min-w-0 flex-1 ${stat.color}`} viewBox="0 0 22 20" fill="none" aria-hidden="true">
                <path d={stat.path} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
