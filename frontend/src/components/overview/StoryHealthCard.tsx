"use client"

import Link from "next/link"

import { ErrorCard } from "@/components/ui/ErrorCard"
import type { StoryHealth } from "@/types/book"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import { panelClass } from "./utils"

export function StoryHealthCard({
  bookId,
  isDark,
  storyHealth,
  storyHealthError,
  onRetryStoryHealth,
}: {
  bookId: string
  isDark: boolean
  storyHealth: StoryHealth | null
  storyHealthError?: boolean
  onRetryStoryHealth?: () => void
}) {
  if (storyHealthError && !storyHealth && onRetryStoryHealth) {
    return (
      <section className={panelClass(isDark, "p-4 sm:p-5")}>
        <PanelTitle isDark={isDark}>Story Health</PanelTitle>
        <div className="mt-4">
          <ErrorCard
            message="Failed to load story health"
            onRetry={onRetryStoryHealth}
            variant="compact"
            isDark={isDark}
          />
        </div>
      </section>
    )
  }

  const healthAvailable = Boolean(storyHealth && storyHealth.available !== false)
  const score = healthAvailable ? storyHealth!.score : 0
  const status = storyHealth?.status ?? "Not available"
  const summary = storyHealth?.summary ?? "Story health needs analyzed manuscript evidence before a score can be calculated."
  const healthColor = score >= 85 ? "#45d483" : score >= 70 ? "#8b5cf6" : score >= 55 ? "#f5bf3d" : "#fb7185"
  const metricColors: Record<string, { text: string; bar: string }> = {
    Continuity: { text: "text-emerald-400", bar: "bg-emerald-400" },
    "Character consistency": { text: "text-sky-400", bar: "bg-sky-400" },
    "Timeline clarity": { text: "text-teal-700", bar: "bg-teal-600" },
    "Plot thread closure": { text: "text-amber-400", bar: "bg-amber-400" },
    "Worldbuilding consistency": { text: "text-cyan-400", bar: "bg-cyan-400" },
    Pacing: { text: "text-rose-400", bar: "bg-rose-400" },
    "Dialogue/voice consistency": { text: "text-fuchsia-400", bar: "bg-fuchsia-400" },
  }
  const metrics = storyHealth?.metrics ?? []

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex items-center gap-2">
        <PanelTitle isDark={isDark}>Story Health</PanelTitle>
        <span className={`flex h-4 w-4 items-center justify-center rounded-full border text-3xs ${isDark ? "border-white/15 text-slate-500" : "border-slate-200 text-slate-400"}`}>i</span>
      </div>

      <div className="mt-5 grid gap-5 sm:grid-cols-[8.5rem_minmax(0,1fr)] xl:grid-cols-1 2xl:grid-cols-[8.5rem_minmax(0,1fr)]">
        <div className="flex justify-center">
          {healthAvailable ? (
            <div
              className="relative flex h-32 w-32 items-center justify-center rounded-full"
              style={{ background: `conic-gradient(${healthColor} 0 ${score}%, ${isDark ? "#1b2430" : "#edf0f5"} ${score}% 100%)` }}
            >
              <div className={`flex h-22 w-22 flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
                <span className={`text-3xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{score}</span>
                <span className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>{status}</span>
              </div>
            </div>
          ) : (
            <div className={`flex h-32 w-32 items-center justify-center rounded-full border px-3 text-center text-xs ${isDark ? "border-white/10 text-slate-400" : "border-slate-200 text-slate-500"}`}>
              Not enough data
            </div>
          )}
        </div>

        <div className="space-y-3">
          {metrics.map((metric) => {
            const colors = metricColors[metric.label] ?? { text: "text-teal-700", bar: "bg-teal-600" }
            return (
              <div key={metric.label} className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/70"}`}>
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className={isDark ? "text-slate-300" : "text-slate-700"}>{metric.label}</span>
                  <span className={`font-bold ${colors.text}`}>{metric.available === false ? "Unavailable" : `${metric.score}%`}</span>
                </div>
                {metric.available !== false ? <div className={`mt-2 h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-200"}`}>
                  <div
                    className={`h-full rounded-full ${colors.bar}`}
                    style={{ width: `${metric.score}%` }}
                  />
                </div> : null}
                <p className={`mt-2 text-3xs leading-5 ${isDark ? "text-slate-500" : "text-slate-500"}`}>{metric.detail}</p>
              </div>
            )
          })}
        </div>
      </div>

      <p className={`mt-5 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{summary}</p>
      <Link href={`/${bookId}/analysis`} className={`mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md text-xs font-semibold transition ${isDark ? "bg-teal-800/10 text-teal-200 hover:bg-teal-800/18" : "bg-teal-50 text-teal-800 hover:bg-teal-100"}`}>
        <Icon name="analysis" className="h-4 w-4" />
        View Full Analysis
      </Link>
    </section>
  )
}
