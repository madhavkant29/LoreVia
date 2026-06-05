"use client"

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"

import type { ToastMessage } from "@/types/ux"

type ToastInput = Omit<ToastMessage, "id">
type ToastContextValue = {
  notify: (message: ToastInput) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const toneClass = {
  default: "border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))] text-[rgb(var(--card-foreground))]",
  success: "border-teal-500/25 bg-teal-500/10 text-[rgb(var(--foreground))]",
  warning: "border-amber-500/30 bg-amber-500/10 text-[rgb(var(--foreground))]",
  danger: "border-red-500/30 bg-red-500/10 text-[rgb(var(--foreground))]",
}

export function StatusToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([])

  const notify = useCallback((message: ToastInput) => {
    const id = `${Date.now()}:${Math.random().toString(36).slice(2)}`
    setMessages((current) => [...current, { ...message, id }].slice(-3))
    window.setTimeout(() => {
      setMessages((current) => current.filter((item) => item.id !== id))
    }, 3600)
  }, [])

  const value = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-5 right-5 z-[90] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-3" aria-live="polite">
        {messages.map((message) => (
          <div
            key={message.id}
            role="status"
            className={`rounded-lg border px-4 py-3 text-sm shadow-[var(--shadow-dropdown)] ${toneClass[message.tone ?? "default"]}`}
          >
            {message.title ? <p className="font-semibold">{message.title}</p> : null}
            <p className={message.title ? "mt-1 leading-6 text-[rgb(var(--muted-foreground))]" : "leading-6"}>{message.body}</p>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useStatusToast() {
  const context = useContext(ToastContext)
  return context?.notify ?? (() => undefined)
}
