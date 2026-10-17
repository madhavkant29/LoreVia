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
  variant = "panel",
}: {
  title?: string
  items: RecentActivityItem[]
  emptyLabel?: string
  variant?: "panel" | "compact"
}) {
  const compact = variant === "compact"

  return (
    <section className={compact ? "border-y border-[rgb(var(--border))] py-3" : "app-panel app-panel--subtle p-5"}>
      <div className="flex items-center justify-between gap-3">
        <p className={compact ? "text-sm font-semibold text-[rgb(var(--foreground))]" : "app-eyebrow"}>{title}</p>
        <span className="text-xs text-[rgb(var(--muted-foreground))]">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className={`${compact ? "mt-2" : "mt-4"} text-sm leading-6 text-[rgb(var(--muted-foreground))]`}>{emptyLabel}</p>
      ) : (
        <div className={compact ? "mt-2 grid sm:grid-cols-3" : "mt-4 space-y-3"}>
          {items.slice(0, compact ? 3 : 5).map((item) => {
            const content = (
              <div className={compact
                ? "flex h-full gap-3 border-t border-[rgb(var(--border))] py-3 transition-colors hover:bg-[rgba(var(--muted),0.25)] sm:border-l sm:border-t-0 sm:px-4 sm:first:border-l-0 sm:first:pl-0"
                : "flex gap-3 rounded-md bg-[rgba(var(--card),0.72)] px-3 py-3 transition-colors hover:bg-[rgba(var(--muted),0.4)]"}
              >
                <span className={`mt-2 h-2 w-2 shrink-0 rounded-full ${toneDot[item.tone ?? "default"]}`} />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-[rgb(var(--foreground))]">{item.label}</span>
                  {item.detail ? <span className="mt-1 block text-xs leading-5 text-[rgb(var(--muted-foreground))]">{item.detail}</span> : null}
                </span>
              </div>
            )
            return item.href ? (
              <Link key={item.id} href={item.href} className="min-w-0">
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
