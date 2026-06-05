"use client"

import Link from "next/link"

import type { RecentActivityItem } from "@/types/ux"

const toneDot = {
  default: "bg-slate-400",
  success: "bg-teal-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
}

export function RecentActivityList({
  title = "Recent activity",
  items,
  emptyLabel = "No recent activity yet.",
}: {
  title?: string
  items: RecentActivityItem[]
  emptyLabel?: string
}) {
  return (
    <section className="app-panel app-panel--subtle p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="app-eyebrow">{title}</p>
        <span className="text-xs text-[rgb(var(--muted-foreground))]">{items.length} signals</span>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm leading-7 text-[rgb(var(--muted-foreground))]">{emptyLabel}</p>
      ) : (
        <div className="mt-4 space-y-3">
          {items.slice(0, 5).map((item) => {
            const content = (
              <div className="flex gap-3 rounded-md border border-[rgba(var(--border),0.72)] bg-[rgba(var(--card),0.72)] px-3 py-3 transition hover:bg-[rgba(var(--muted),0.4)]">
                <span className={`mt-2 h-2 w-2 shrink-0 rounded-full ${toneDot[item.tone ?? "default"]}`} />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-[rgb(var(--foreground))]">{item.label}</span>
                  {item.detail ? <span className="mt-1 block text-xs leading-5 text-[rgb(var(--muted-foreground))]">{item.detail}</span> : null}
                </span>
              </div>
            )
            return item.href ? (
              <Link key={item.id} href={item.href}>
                {content}
              </Link>
            ) : (
              <div key={item.id}>{content}</div>
            )
          })}
        </div>
      )}
    </section>
  )
}
