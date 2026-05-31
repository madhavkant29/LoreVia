"use client"

import { buildIssueDisplay } from "@/lib/utils/storyFeedback"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import type { IconName } from "./types"
import { panelClass, severityClass } from "./utils"

export function ActiveIssuesCard({
  isDark,
  continuityIssueCount,
  worldGapCount,
  timelineIssueCount,
  onNavigate,
  bookId,
}: {
  isDark: boolean
  continuityIssueCount: number
  worldGapCount: number
  timelineIssueCount: number
  onNavigate: (href: string) => void
  bookId: string
}) {
  const issues = [
    { title: "Character Inconsistencies", rawCount: continuityIssueCount, severity: "High", icon: "users" as IconName, color: "text-rose-400", href: `/${bookId}/reports` },
    { title: "World Gaps", rawCount: worldGapCount, severity: "Medium", icon: "gap" as IconName, color: "text-amber-400", href: `/${bookId}/world-gap` },
    { title: "Timeline Conflicts", rawCount: timelineIssueCount, severity: "Low", icon: "timeline" as IconName, color: "text-teal-700", href: `/${bookId}/timeline` },
  ].map((issue) => ({
    ...issue,
    ...buildIssueDisplay(issue.rawCount),
  }))
  const totalDisplayedIssues = issues.reduce((sum, issue) => sum + issue.displayCount, 0)

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex items-center gap-2">
        <PanelTitle isDark={isDark}>Active Issues</PanelTitle>
        <span className="rounded-full bg-rose-500 px-1.5 py-0.5 text-3xs font-bold leading-none text-white">{totalDisplayedIssues}</span>
      </div>

      <div className="mt-4 space-y-3">
        {issues.map((issue) => (
          <button
            key={issue.title}
            onClick={() => onNavigate(issue.href)}
            className={`flex w-full items-center gap-3 rounded-md border p-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.025] hover:bg-white/[0.05]" : "border-slate-100 bg-white hover:bg-slate-50"}`}
          >
            <Icon name={issue.icon} className={`h-6 w-6 ${issue.color}`} />
            <div className="min-w-0 flex-1">
              <p className={`truncate text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>{issue.title}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{issue.label}</p>
            </div>
            <span className={`rounded px-2 py-1 text-3xs font-semibold ${severityClass(issue.severity, isDark)}`}>{issue.severity}</span>
            <Icon name="chevron" className={isDark ? "h-3.5 w-3.5 text-slate-600" : "h-3.5 w-3.5 text-slate-400"} />
          </button>
        ))}
      </div>

      <button onClick={() => onNavigate(`/${bookId}/analysis`)} className="mt-5 inline-flex w-full items-center justify-end gap-2 text-xs font-semibold text-teal-800">
        Go to Insights
        <Icon name="chevron" className="h-3.5 w-3.5" />
      </button>
    </section>
  )
}
