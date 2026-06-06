"use client"

import { useEffect, useState } from "react"

import { Button } from "@/components/ui/Button"
import { GLOBAL_SHORTCUTS } from "@/lib/utils/shortcuts"

const DISMISS_KEY = "lorevia-shortcut-help-dismissed:v1"

export function ShortcutHelp() {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "?" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        setOpen((current) => !current)
      }
      if (event.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  if (!open) return null

  return (
    <div className="fixed bottom-5 left-5 z-[70] max-w-sm rounded-lg border border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))] p-4 text-[rgb(var(--card-foreground))] shadow-[var(--shadow-dropdown)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="app-eyebrow">Shortcuts</p>
          <p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">Press ? anytime to reopen this guide.</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setOpen(false)
            window.localStorage.setItem(DISMISS_KEY, "true")
          }}
        >
          Dismiss
        </Button>
      </div>
      <div className="mt-4 space-y-2">
        {GLOBAL_SHORTCUTS.map((shortcut) => (
          <div key={shortcut.id} className="flex items-center justify-between gap-4 text-sm">
            <span>{shortcut.label}</span>
            <kbd className="rounded-md border border-[rgba(var(--border),0.9)] px-2 py-1 text-xs text-[rgb(var(--muted-foreground))]">
              {shortcut.keys}
            </kbd>
          </div>
        ))}
      </div>
    </div>
  )
}
