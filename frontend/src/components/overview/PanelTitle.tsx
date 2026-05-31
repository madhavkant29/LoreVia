import React from "react"

export function PanelTitle({ isDark, children }: { isDark: boolean; children: React.ReactNode }) {
  return <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{children}</h2>
}
