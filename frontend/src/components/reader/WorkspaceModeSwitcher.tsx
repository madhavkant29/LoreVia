"use client"

import { HelpBubble } from "@/components/ui/HelpBubble"
import { cn } from "@/lib/utils/text"

export function WorkspaceModeSwitcher({
  activeMode,
  modeSaving,
  writingAvailable,
  writingUnavailableReason = "Writing workspace requires an Author plan or manuscript editing permission.",
  isDark,
  onModeChange,
}: {
  activeMode: "reader" | "author"
  modeSaving: boolean
  writingAvailable: boolean
  writingUnavailableReason?: string
  isDark: boolean
  onModeChange: (nextMode: "reader" | "author") => void
}) {
  const options = [
    { value: "reader" as const, label: "Reading workspace", short: "Reading", description: "Read chapters, use recaps and notes, and stay spoiler-safe." },
    { value: "author" as const, label: "Writing workspace", short: "Writing", description: "Edit the manuscript, use the story bible and analysis, and manage sharing." },
  ]

  return (
    <div className="max-w-full">
      <div className="mb-1.5 flex items-center gap-1 text-xs text-[rgb(var(--muted-foreground))]">
        <span>Switching changes the tools you see, never your book content.</span>
        <HelpBubble label="About Reading and Writing workspaces">
          <span className="font-semibold">Reading workspace</span> is for reading, recaps, notes, and spoiler-safe tools. <span className="font-semibold">Writing workspace</span> is for editing, story intelligence, and sharing.
        </HelpBubble>
      </div>
      <div role="group" aria-label="Choose Reading or Writing workspace" className={cn("inline-grid max-w-full grid-cols-2 rounded-sm p-1", isDark ? "bg-white/[0.04]" : "bg-slate-100")}>
        {options.map((option) => {
          const disabled = modeSaving || (option.value === "author" && !writingAvailable)
          const unavailableReason = option.value === "author" && !writingAvailable ? writingUnavailableReason : undefined
          return (
            <button
              key={option.value}
              type="button"
              disabled={disabled}
              aria-pressed={activeMode === option.value}
              aria-label={option.label}
              title={unavailableReason ?? option.description}
              onClick={() => onModeChange(option.value)}
              className={cn(
                "min-h-10 rounded-sm px-3 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/60 disabled:cursor-not-allowed disabled:opacity-55 sm:px-4",
                activeMode === option.value
                  ? "bg-teal-800 text-white"
                  : isDark ? "text-slate-300 hover:bg-white/[0.06]" : "text-slate-600 hover:bg-white",
              )}
            >
              <span className="sm:hidden">{option.short}</span>
              <span className="hidden sm:inline">{option.label}</span>
            </button>
          )
        })}
      </div>
      {!writingAvailable ? <p className={cn("mt-1.5 text-xs", isDark ? "text-amber-300" : "text-amber-800")}>{writingUnavailableReason}</p> : null}
    </div>
  )
}
