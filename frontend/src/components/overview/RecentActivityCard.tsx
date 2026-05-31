"use client"

import Link from "next/link"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import { panelClass } from "./utils"

export function RecentActivityCard({
  isDark,
}: {
  isDark: boolean
}) {
  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Recent Activity</PanelTitle>
      <div className="mt-4">
        <p
          className={`rounded-md border border-dashed px-4 py-5 text-sm ${
            isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-500"
          }`}
        >
          No recent activity yet. Start writing or reading to see your activity here.
        </p>
      </div>
      <Link
        href="/notifications"
        className="mt-5 inline-flex w-full items-center justify-end gap-2 text-xs font-semibold text-teal-800"
      >
        View All Activity
        <Icon name="chevron" className="h-3.5 w-3.5" />
      </Link>
    </section>
  )
}
