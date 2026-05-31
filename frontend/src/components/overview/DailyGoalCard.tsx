"use client"

import Link from "next/link"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import { clamp, panelClass } from "./utils"

export function DailyGoalCard({ isDark, dailyWords, dailyTarget }: { isDark: boolean; dailyWords: number; dailyTarget: number }) {
  const goalPercent = clamp((dailyWords / dailyTarget) * 100, 0, 100)
  const progressLabel =
    dailyWords >= dailyTarget
      ? "Goal reached today."
      : dailyWords > 0
        ? "Progress updates when you save manuscript edits."
        : "No writing logged yet today."

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Daily Goal</PanelTitle>
      <div className="mt-6 flex items-center justify-center">
        <div
          className="relative flex h-32 w-32 items-center justify-center rounded-full"
          style={{ background: `conic-gradient(#8b5cf6 0 ${goalPercent}%, ${isDark ? "#1b2430" : "#edf0f5"} ${goalPercent}% 100%)` }}
        >
          <div className={`flex h-24 w-24 flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
            <span className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{dailyWords.toLocaleString()}</span>
            <span className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>/ {dailyTarget.toLocaleString()} words</span>
          </div>
        </div>
      </div>
      <div className="mt-5 flex items-center justify-between gap-3">
        <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>{progressLabel}</p>
        <Link href="/settings" className={`rounded-md px-3 py-2 text-xs font-semibold ${isDark ? "bg-teal-800/10 text-teal-200" : "bg-teal-50 text-teal-800"}`}>Update Goal</Link>
      </div>
    </section>
  )
}
