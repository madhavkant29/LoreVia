"use client"

import type { ReactNode } from "react"

import { cn } from "@/lib/utils/text"
import type { NormalizedProcessingStatus } from "@/lib/utils/processingStatus"
import type { SaveState } from "@/types/book"

type ProcessingStatusProps = {
  status: NormalizedProcessingStatus | null
  onRetry?: () => void
  retrying?: boolean
  className?: string
}

export function ProcessingStatusStrip({ status, onRetry, retrying = false, className }: ProcessingStatusProps) {
  if (!status || status.ready) return null
  const progress = status.progressPct ?? (status.partialReady ? 35 : 8)
  const actionLabel = status.resumeAvailable ? "Continue processing" : "Retry"
  const pendingLabel = status.resumeAvailable ? "Continuing..." : "Retrying..."

  return (
    <div className={cn("rounded-md border border-border bg-card/60 p-3", className)} role="status">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-[rgb(var(--foreground))]">{status.label}</p>
          {status.detail ? <p className="mt-1 text-xs text-[rgb(var(--muted-foreground))]">{status.detail}</p> : null}
        </div>
        {status.retryAvailable && onRetry ? (
          <button type="button" className="app-button-secondary min-h-9 px-3 text-xs" onClick={onRetry} disabled={retrying}>
            {retrying ? pendingLabel : actionLabel}
          </button>
        ) : null}
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", status.failed ? "bg-amber-400" : "bg-[rgb(var(--accent))]")} style={{ width: `${progress}%` }} />
      </div>
    </div>
  )
}

export function ProcessingStatusPanel({ status, onRetry, retrying = false, className }: ProcessingStatusProps) {
  if (!status || status.ready) return null
  const actionLabel = status.resumeAvailable ? "Continue processing" : "Retry processing"
  const pendingLabel = status.resumeAvailable ? "Continuing..." : "Retrying..."

  return (
    <section className={cn("app-panel app-panel--subtle p-4", className)} role="status" aria-live="polite">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[rgb(var(--foreground))]">{status.label}</p>
          <p className="mt-1 text-sm leading-6 text-[rgb(var(--muted-foreground))]">
            {status.partialReady ? "First chapters ready. Character extraction may still be running. You can start reading/editing now." : status.detail}
          </p>
          {status.lastError ? <p className="mt-2 text-xs text-amber-500">{status.lastError}</p> : null}
        </div>
        {status.retryAvailable && onRetry ? (
          <button type="button" className="app-button-secondary shrink-0" onClick={onRetry} disabled={retrying}>
            {retrying ? pendingLabel : actionLabel}
          </button>
        ) : null}
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full", status.failed ? "bg-amber-400" : "bg-[rgb(var(--accent))]")}
          style={{ width: `${status.progressPct ?? (status.partialReady ? 35 : 8)}%` }}
        />
      </div>
    </section>
  )
}

export function SaveStatePill({ state, className }: { state: SaveState; className?: string }) {
  const copy: Record<SaveState, string> = {
    saved: "Saved",
    saving: "Saving...",
    offline_draft: "Offline draft",
    retrying: "Retrying...",
    error: "Could not save",
  }
  return (
    <span className={cn("inline-flex min-h-7 items-center rounded-full border px-3 text-xs font-semibold", saveStateClass(state), className)}>
      {copy[state]}
    </span>
  )
}

export function LastSavedLabel({ value, fallback = "Not saved yet", className }: { value?: string | Date | null; fallback?: string; className?: string }) {
  const label = value ? `Last saved ${formatSavedTime(value)}` : fallback
  return <span className={cn("text-xs text-[rgb(var(--muted-foreground))]", className)}>{label}</span>
}

export function RecoverableInlineError({
  message,
  actionLabel = "Try again",
  onAction,
  children,
  className,
}: {
  message: string
  actionLabel?: string
  onAction?: () => void
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn("rounded-md border border-amber-500/25 bg-amber-500/[0.04] p-3 text-sm text-[rgb(var(--foreground))]", className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium">{message}</p>
          {children ? <div className="mt-1 text-xs text-[rgb(var(--muted-foreground))]">{children}</div> : null}
        </div>
        {onAction ? (
          <button type="button" className="app-button-secondary min-h-9 px-3 text-xs" onClick={onAction}>
            {actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  )
}

function saveStateClass(state: SaveState) {
  switch (state) {
    case "saved":
      return "border-emerald-500/25 bg-emerald-500/[0.08] text-emerald-600"
    case "saving":
    case "retrying":
      return "border-sky-500/25 bg-sky-500/[0.08] text-sky-600"
    case "offline_draft":
      return "border-amber-500/25 bg-amber-500/[0.08] text-amber-600"
    case "error":
      return "border-rose-500/25 bg-rose-500/[0.08] text-rose-600"
  }
}

function formatSavedTime(value: string | Date) {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return "just now"
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
}
