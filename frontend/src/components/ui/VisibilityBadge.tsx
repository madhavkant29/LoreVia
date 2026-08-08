import { BookOpen, LockKeyhole, MessageSquareText, Users } from "lucide-react"

import { cn } from "@/lib/utils/text"

export type VisibilityBadgeState =
  | "private"
  | "shared"
  | "beta_readers"
  | "public_sample"
  | "public_discussion"

const BADGE_META = {
  private: {
    label: "Private",
    icon: LockKeyhole,
    className: "border-slate-400/30 bg-slate-500/10 text-slate-600 dark:text-slate-300",
  },
  shared: {
    label: "Shared",
    icon: Users,
    className: "border-blue-400/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
  },
  beta_readers: {
    label: "Beta readers",
    icon: MessageSquareText,
    className: "border-amber-400/35 bg-amber-500/10 text-amber-800 dark:text-amber-300",
  },
  public_sample: {
    label: "Public sample",
    icon: BookOpen,
    className: "border-emerald-400/35 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
  },
  public_discussion: {
    label: "Public discussion",
    icon: MessageSquareText,
    className: "border-cyan-400/35 bg-cyan-500/10 text-cyan-800 dark:text-cyan-300",
  },
} as const

export function VisibilityBadge({
  state,
  label,
  className,
}: {
  state: VisibilityBadgeState
  label?: string
  className?: string
}) {
  const meta = BADGE_META[state]
  const Icon = meta.icon
  return (
    <span
      className={cn(
        "inline-flex min-h-7 items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold tracking-normal",
        meta.className,
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label ?? meta.label}
    </span>
  )
}
