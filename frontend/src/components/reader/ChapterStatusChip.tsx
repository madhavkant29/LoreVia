"use client"

type ChapterStatusTone = "processed" | "queued" | "read" | "unread" | "intel-ready" | "intel-locked"

type ChapterStatusChipProps = {
  label: string
  tone: ChapterStatusTone
  isDark: boolean
}

const CHIP_STYLES: Record<ChapterStatusTone, { dark: string; light: string }> = {
  processed: {
    dark: "border border-teal-400/15 bg-teal-400/12 text-teal-200",
    light: "border border-teal-200 bg-teal-50 text-teal-700",
  },
  queued: {
    dark: "border border-amber-400/15 bg-amber-400/12 text-amber-200",
    light: "border border-amber-200 bg-amber-50 text-amber-700",
  },
  read: {
    dark: "border border-sky-400/15 bg-sky-400/12 text-sky-200",
    light: "border border-sky-200 bg-sky-50 text-sky-700",
  },
  unread: {
    dark: "border border-white/10 bg-white/[0.06] text-slate-300",
    light: "border border-stone-200 bg-stone-100 text-stone-600",
  },
  "intel-ready": {
    dark: "border border-violet-400/15 bg-violet-400/12 text-violet-200",
    light: "border border-violet-200 bg-violet-50 text-violet-700",
  },
  "intel-locked": {
    dark: "border border-white/10 bg-white/[0.06] text-slate-400",
    light: "border border-stone-200 bg-stone-100 text-stone-500",
  },
}

export function ChapterStatusChip({ label, tone, isDark }: ChapterStatusChipProps) {
  const palette = CHIP_STYLES[tone]

  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-3xs font-semibold tracking-[0.01em] ${isDark ? palette.dark : palette.light}`}
    >
      {label}
    </span>
  )
}
