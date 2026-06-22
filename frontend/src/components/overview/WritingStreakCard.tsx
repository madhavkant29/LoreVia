"use client"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import { panelClass } from "./utils"

export function WritingStreakCard({ isDark, streakDays, weekActivity, compact = false }: { isDark: boolean; streakDays: number; weekActivity: boolean[]; compact?: boolean }) {
  return (
    <section className={compact ? "min-w-0" : panelClass(isDark, "h-full p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Writing streak</PanelTitle>
      <div className="mt-5 flex items-center gap-3">
        <Icon name="flame" className="h-8 w-8 text-orange-400" />
        <div>
          <p className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{streakDays} days</p>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Tracked from daily sign-ins.</p>
        </div>
      </div>
      <div className="mt-6 grid grid-cols-7 gap-2">
        {["M", "T", "W", "T", "F", "S", "S"].map((day, index) => (
          <div key={`${day}-${index}`} className="text-center">
            <div className={`mx-auto h-9 w-4 rounded-full ${weekActivity[index] ? "bg-teal-800" : isDark ? "bg-white/10" : "bg-slate-200"}`} />
            <p className={`mt-2 text-3xs font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>{day}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
