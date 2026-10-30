"use client"

import { HelpCircle, Info, X } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"

import { cn } from "@/lib/utils/text"

export function HelpBubble({
  label,
  children,
  className,
  icon = "help",
}: {
  label: string
  children: React.ReactNode
  className?: string
  icon?: "help" | "info"
}) {
  const [open, setOpen] = useState(false)
  const descriptionId = useId()
  const rootRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const closeOnOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    document.addEventListener("pointerdown", closeOnOutside)
    document.addEventListener("keydown", closeOnEscape)
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside)
      document.removeEventListener("keydown", closeOnEscape)
    }
  }, [open])

  return (
    <span ref={rootRef} className={cn("relative inline-flex", className)}>
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? descriptionId : undefined}
        onClick={() => setOpen(true)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        className="inline-flex h-7 w-7 items-center justify-center rounded-sm text-[rgb(var(--foreground))] transition hover:bg-[rgba(var(--border),0.35)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--accent))]"
      >
        {icon === "info" ? <Info className="h-4 w-4" aria-hidden="true" /> : <HelpCircle className="h-4 w-4" aria-hidden="true" />}
      </button>
      {open ? (
        <span
          id={descriptionId}
          role="tooltip"
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          className="absolute left-1/2 top-full z-[80] mt-2 w-72 -translate-x-1/2 rounded-none border border-[rgb(var(--border))] bg-[rgb(var(--surface))] p-3 text-left text-xs leading-5 text-[rgb(var(--foreground))] shadow-[var(--shadow-dropdown)]"
        >
          <span className="flex items-start gap-2">
            <span className="min-w-0 flex-1">{children}</span>
            <button type="button" aria-label="Close help" onClick={() => setOpen(false)} className="shrink-0 rounded-sm p-0.5 hover:bg-[rgba(var(--border),0.35)]">
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </span>
        </span>
      ) : null}
    </span>
  )
}
