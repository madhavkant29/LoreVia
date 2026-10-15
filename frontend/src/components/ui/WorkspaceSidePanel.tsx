"use client"

import { useSyncExternalStore, type ReactNode } from "react"
import { Dialog } from "@/components/ui/Dialog"

const desktopQuery = "(min-width: 1280px)"

function subscribeToDesktop(callback: () => void) {
  const media = window.matchMedia(desktopQuery)
  media.addEventListener("change", callback)
  return () => media.removeEventListener("change", callback)
}

export function WorkspaceSidePanel({ title, side, onClose, children, open = true }: {
  title: string
  side: "left" | "right"
  onClose: () => void
  children: ReactNode
  open?: boolean
}) {
  const desktop = useSyncExternalStore(subscribeToDesktop, () => window.matchMedia(desktopQuery).matches, () => false)
  if (desktop) return <div className="min-w-0" aria-label={title}>{children}</div>
  if (!open) return null

  return (
    <Dialog
      open
      onClose={onClose}
      title={title}
      description="Close this panel to return to your work."
      descriptionClassName="sr-only"
      titleClassName="sticky top-0 z-10 m-0 border-b border-[rgb(var(--border))] bg-[rgb(var(--card))] px-4 py-4 pr-24 text-sm"
      contentClassName="p-0"
      className={`top-3 h-[calc(100dvh-1.5rem)] max-h-none w-[calc(100%-1.5rem)] max-w-sm translate-x-0 translate-y-0 rounded-sm ${side === "left" ? "left-3" : "left-auto right-3"}`}
    >
      <button type="button" onClick={onClose} className="absolute right-3 top-1.5 z-20 min-h-11 px-3 text-sm underline underline-offset-4">Close</button>
      {children}
    </Dialog>
  )
}
