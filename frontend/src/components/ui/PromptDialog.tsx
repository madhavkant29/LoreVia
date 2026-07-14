"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/Button"
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
  const previousFocusRef = useRef<HTMLElement | null>(null)

  const close = useCallback((value: string | null) => {
    setPending((current) => {
      current?.resolve(value)
      return null
    })
    window.setTimeout(() => previousFocusRef.current?.focus(), 0)
  }, [])

  const prompt = useCallback((config: PromptDialogConfig) => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
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

  if (!pending) return null

  const descriptionId = pending.body ? "prompt-dialog-description" : undefined
  const errorId = error ? "prompt-dialog-error" : undefined
  const inputId = "prompt-dialog-input"

  const submit = () => {
    const nextError = pending.validate?.(value) ?? null
    if (nextError) {
      setError(nextError)
      return
    }
    onClose(value)
  }

  const fieldClass = "mt-2 w-full rounded-md border border-[rgba(var(--border),0.9)] bg-[rgb(var(--background))] px-3 py-2 text-sm text-[rgb(var(--foreground))] outline-none transition focus:ring-2 focus:ring-teal-300/50"

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 px-4 py-6" role="presentation">
      <section
        aria-modal="true"
        role="dialog"
        aria-labelledby="prompt-dialog-title"
        aria-describedby={descriptionId}
        className="w-full max-w-lg rounded-lg border border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))] p-6 text-[rgb(var(--card-foreground))] shadow-[var(--shadow-modal)]"
      >
        <p className="app-eyebrow">Input required</p>
        <h2 id="prompt-dialog-title" className="mt-3 text-2xl font-semibold tracking-tight">
          {pending.title}
        </h2>
        {pending.body ? (
          <div id={descriptionId} className="mt-4 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
            {pending.body}
          </div>
        ) : null}
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
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={() => onClose(null)}>
            {pending.cancelLabel ?? "Cancel"}
          </Button>
          <Button type="button" variant="primary" onClick={submit}>
            {pending.confirmLabel ?? "Continue"}
          </Button>
        </div>
      </section>
    </div>
  )
}
