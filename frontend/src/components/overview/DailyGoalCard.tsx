"use client"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import { clamp, panelClass } from "./utils"

export function DailyGoalCard({ isDark, dailyWords, dailyTarget, onUpdateGoal }: { isDark: boolean; dailyWords: number; dailyTarget: number; onUpdateGoal?: () => void }) {
  const goalPercent = clamp((dailyWords / dailyTarget) * 100, 0, 100)
  const progressLabel = dailyWords >= dailyTarget
    ? "Goal reached today."
    : dailyWords > 0
      ? "Progress updates when you save manuscript edits."
      : "No writing logged yet today."

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Daily goal</PanelTitle>
      <div className="mt-6 flex items-center justify-center">
        <div
          className="relative flex h-32 w-32 items-center justify-center rounded-full"
          style={{ background: `conic-gradient(#8b5cf6 0 ${goalPercent}%, ${isDark ? "#1b2430" : "#edf0f5"} ${goalPercent}% 100%)` }}
        >
          <div className={`flex h-24 w-24 flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
            <span className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{dailyWords.toLocaleString()}</span>
            <span className={`text-3xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>/ {dailyTarget.toLocaleString()} words</span>
          </div>
        </div>
      </div>
      <p className={`mt-5 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>{progressLabel}</p>
      {onUpdateGoal ? <button type="button" onClick={onUpdateGoal} className={`mt-3 inline-flex w-full items-center justify-between border-t pt-4 text-xs font-semibold ${isDark ? "border-white/10 text-teal-300" : "border-slate-100 text-teal-700"}`}>Update goal <Icon name="chevron" /></button> : null}
    </section>
  )
}
