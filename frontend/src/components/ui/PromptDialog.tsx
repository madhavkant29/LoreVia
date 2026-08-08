"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/Button"
import { Dialog } from "@/components/ui/Dialog"
import type { PromptDialogConfig } from "@/types/ux"

type PendingPrompt = PromptDialogConfig & {
  resolve: (value: string | null) => void
}

type PromptContextValue = {
  prompt: (config: PromptDialogConfig) => Promise<string | null>
}

const PromptContext = createContext<PromptContextValue | null>(null)

export function PromptDialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingPrompt | null>(null)

  const close = useCallback((value: string | null) => {
    setPending((current) => {
      current?.resolve(value)
      return null
    })
  }, [])

  const prompt = useCallback((config: PromptDialogConfig) => {
    return new Promise<string | null>((resolve) => {
      setPending({ ...config, resolve })
    })
  }, [])

  const value = useMemo(() => ({ prompt }), [prompt])

  return (
    <PromptContext.Provider value={value}>
      {children}
      <PromptDialog pending={pending} onClose={close} />
    </PromptContext.Provider>
  )
}

export function usePromptDialog() {
  const context = useContext(PromptContext)
  if (context) return context.prompt

  return async () => null
}

function PromptDialog({
  pending,
  onClose,
}: {
  pending: PendingPrompt | null
  onClose: (value: string | null) => void
}) {
  const [value, setValue] = useState("")
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null)

  useEffect(() => {
    setValue(pending?.initialValue ?? "")
    setError(null)
    if (pending) window.setTimeout(() => inputRef.current?.focus(), 0)
  }, [pending])

  const errorId = error ? "prompt-dialog-error" : undefined
  const inputId = "prompt-dialog-input"

  const submit = () => {
    if (!pending) return
    const nextError = pending.validate?.(value) ?? null
    if (nextError) {
      setError(nextError)
      return
    }
    onClose(value)
  }

  const fieldClass = "mt-2 w-full rounded-md border border-[rgba(var(--border),0.9)] bg-[rgb(var(--background))] px-3 py-2 text-sm text-[rgb(var(--foreground))] outline-none transition focus:ring-2 focus:ring-teal-300/50"

  return (
    <Dialog
      open={Boolean(pending)}
      onClose={() => onClose(null)}
      title={pending?.title ?? "Input required"}
      description={pending?.body}
      eyebrow="Input required"
      initialFocusRef={inputRef}
      footer={pending ? (
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={() => onClose(null)}>
            {pending.cancelLabel ?? "Cancel"}
          </Button>
          <Button type="button" variant="primary" onClick={submit}>
            {pending.confirmLabel ?? "Continue"}
          </Button>
        </div>
      ) : null}
    >
      {pending ? (
        <>
        <label htmlFor={inputId} className="mt-5 block text-sm font-semibold">
          {pending.label}
        </label>
        {pending.multiline ? (
          <textarea
            ref={(node) => {
              inputRef.current = node
            }}
            id={inputId}
            value={value}
            placeholder={pending.placeholder}
            rows={8}
            aria-invalid={error ? "true" : "false"}
            aria-describedby={errorId}
            onKeyDown={(event) => {
              if (event.key === "Escape") onClose(null)
            }}
            onChange={(event) => {
              setValue(event.target.value)
              setError(null)
            }}
            className={fieldClass}
          />
        ) : (
          <input
            ref={(node) => {
              inputRef.current = node
            }}
            id={inputId}
            value={value}
            placeholder={pending.placeholder}
            aria-invalid={error ? "true" : "false"}
            aria-describedby={errorId}
            onChange={(event) => {
              setValue(event.target.value)
              setError(null)
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") submit()
              if (event.key === "Escape") onClose(null)
            }}
            className={fieldClass}
          />
        )}
        {error ? (
          <p id={errorId} className="mt-2 text-sm font-semibold text-red-500">
            {error}
          </p>
        ) : null}
        </>
      ) : null}
    </Dialog>
  )
}
