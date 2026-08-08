"use client"

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/Button"
import { Dialog } from "@/components/ui/Dialog"
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

  const close = useCallback((confirmed: boolean) => {
    setPending((current) => {
      current?.resolve(confirmed)
      return null
    })
  }, [])

  const confirm = useCallback((config: ConfirmDialogConfig) => {
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
  const danger = pending?.tone === "danger"
  const cancelRef = useRef<HTMLButtonElement | null>(null)

  return (
    <Dialog
      open={Boolean(pending)}
      onClose={() => onClose(false)}
      title={pending?.title ?? "Confirm action"}
      description={pending?.body}
      eyebrow={danger ? "Confirm destructive action" : "Confirm action"}
      closeOnOutside={!danger}
      initialFocusRef={cancelRef}
      size="sm"
      footer={pending ? (
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button ref={cancelRef} type="button" variant="secondary" onClick={() => onClose(false)}>
            {pending.cancelLabel ?? "Cancel"}
          </Button>
          <Button type="button" variant={danger ? "danger" : "primary"} onClick={() => onClose(true)}>
            {pending.confirmLabel ?? "Confirm"}
          </Button>
        </div>
      ) : null}
    />
  )
}
