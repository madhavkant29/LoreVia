"use client"

import { useEffect, useState } from "react"

type FirstTimeTooltipProps = {
  storageKey: string
  title: string
  message: string
  isDark: boolean
  onDismiss?: () => void
}

export function FirstTimeTooltip({
  storageKey,
  title,
  message,
  isDark,
  onDismiss,
}: FirstTimeTooltipProps) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    // Check if user has seen this tooltip before
    const hasSeenTooltip = localStorage.getItem(storageKey)
    if (!hasSeenTooltip) {
      setIsVisible(true)
    }
  }, [storageKey])

  const handleDismiss = () => {
    localStorage.setItem(storageKey, "true")
    setIsVisible(false)
    onDismiss?.()
  }

  if (!isVisible) return null

  return (
    <div className="mx-auto w-full max-w-[1500px] px-4 pt-5 sm:px-6 lg:px-8">
      <div className="flex justify-end">
      <div
        className={`w-full max-w-md rounded-2xl border p-6 shadow-2xl ${
          isDark
            ? "border-white/10 bg-[#0b0f17] text-slate-100"
            : "border-stone-200 bg-white text-stone-900"
        }`}
      >
        <div className="mb-4">
          <h3
            className={`text-lg font-semibold ${
              isDark ? "text-white" : "text-stone-950"
            }`}
          >
            {title}
          </h3>
        </div>

        <div
          className={`mb-6 text-sm leading-relaxed ${
            isDark ? "text-slate-300" : "text-stone-600"
          }`}
        >
          {message}
        </div>

        <div className="flex justify-end">
          <button
            onClick={handleDismiss}
            className={`rounded-xl px-6 py-2.5 text-sm font-medium transition ${
              isDark
                ? "bg-violet-600 text-white hover:bg-violet-700"
                : "bg-violet-600 text-white hover:bg-violet-700"
            }`}
          >
            Got it
          </button>
        </div>
      </div>
      </div>
    </div>
  )
}
