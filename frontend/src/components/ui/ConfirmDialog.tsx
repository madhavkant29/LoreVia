"use client"

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/Button"
import type { ConfirmDialogConfig } from "@/types/ux"

type PendingConfirm = ConfirmDialogConfig & {
  resolve: (confirmed: boolean) => void
}

type ConfirmContextValue = {
  confirm: (config: ConfirmDialogConfig) => Promise<boolean>
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null)

export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  const close = useCallback((confirmed: boolean) => {
    setPending((current) => {
      current?.resolve(confirmed)
      return null
    })
    window.setTimeout(() => previousFocusRef.current?.focus(), 0)
  }, [])

  const confirm = useCallback((config: ConfirmDialogConfig) => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    return new Promise<boolean>((resolve) => {
      setPending({ ...config, resolve })
    })
  }, [])

  const value = useMemo(() => ({ confirm }), [confirm])

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      <ConfirmDialog pending={pending} onClose={close} />
    </ConfirmContext.Provider>
  )
}

export function useConfirmDialog() {
  const context = useContext(ConfirmContext)
  if (context) return context.confirm

  return async () => false
}

export function ConfirmDialog({
  pending,
  onClose,
}: {
  pending: PendingConfirm | null
  onClose: (confirmed: boolean) => void
}) {
  if (!pending) return null

  const danger = pending.tone === "danger"

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 px-4 py-6" role="presentation">
      <section
        aria-modal="true"
        role="dialog"
        aria-labelledby="confirm-dialog-title"
        className="w-full max-w-md rounded-lg border border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))] p-6 text-[rgb(var(--card-foreground))] shadow-[var(--shadow-modal)]"
      >
        <p className="app-eyebrow">{danger ? "Confirm destructive action" : "Confirm action"}</p>
        <h2 id="confirm-dialog-title" className="mt-3 text-2xl font-semibold tracking-tight">
          {pending.title}
        </h2>
        <div className="mt-4 text-sm leading-7 text-[rgb(var(--muted-foreground))]">{pending.body}</div>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={() => onClose(false)}>
            {pending.cancelLabel ?? "Cancel"}
          </Button>
          <Button type="button" variant={danger ? "danger" : "primary"} onClick={() => onClose(true)}>
            {pending.confirmLabel ?? "Confirm"}
          </Button>
        </div>
      </section>
    </div>
  )
}
