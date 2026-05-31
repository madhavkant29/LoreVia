"use client"

import { cn } from "@/lib/utils/text"

type Props = {
  title?: string
  message: string
  onRetry: () => void
  variant?: "full" | "compact"
  isDark?: boolean
}

export function ErrorCard({ title, message, onRetry, variant = "full", isDark = true }: Props) {
  if (variant === "compact") {
    return (
      <div
        className={cn(
          "rounded-md border border-amber-500/25 bg-amber-500/[0.04] p-4 text-sm",
          isDark ? "text-slate-300" : "text-slate-700"
        )}
      >
        <div className="flex items-start gap-3">
          <AlertIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
          <div className="min-w-0 flex-1">
            <p className="font-medium">{message}</p>
          </div>
          <button
            type="button"
            onClick={onRetry}
            className={cn(
              "shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition",
              isDark
                ? "border border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]"
                : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            )}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn(
        "mx-auto flex max-w-2xl flex-col items-center gap-5 rounded-lg border px-8 py-16 text-center",
        isDark
          ? "border-amber-500/20 bg-[#191d20] text-[#f5f0e8]"
          : "border-amber-300 bg-[#fbfaf7] text-stone-950"
      )}
    >
      <div
        className={cn(
          "flex h-16 w-16 items-center justify-center rounded-full",
          isDark ? "bg-amber-500/10" : "bg-amber-100"
        )}
      >
        <AlertIcon className="h-8 w-8 text-amber-400" />
      </div>

      <div>
        {title ? (
          <h2 className="text-xl font-semibold tracking-[-0.02em]">{title}</h2>
        ) : null}
        <p
          className={cn(
            "mt-2 max-w-md text-sm leading-7",
            isDark ? "text-[#a6a39b]" : "text-stone-600"
          )}
        >
          {message}
        </p>
      </div>

      <button
        type="button"
        onClick={onRetry}
        className={cn(
          "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-6 text-sm font-semibold transition",
          isDark
            ? "bg-[#215f5c] text-white hover:bg-[#1d5552]"
            : "bg-[#1f615d] text-white hover:bg-[#194f4c]"
        )}
      >
        <RefreshIcon className="h-4 w-4" />
        Try again
      </button>
    </div>
  )
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
      />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.8}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182"
      />
    </svg>
  )
}
