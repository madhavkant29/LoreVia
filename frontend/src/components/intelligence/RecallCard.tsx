"use client"
import { useEffect, useState } from "react"

interface Props {
  recall: string
  lastChapter: number
  onDismiss: () => void
  onContinue: () => void
}

export function RecallCard({ recall, lastChapter, onDismiss, onContinue }: Props) {
  const [theme, setTheme] = useState<"light" | "dark">("light")

  useEffect(() => {
    const stored = window.localStorage.getItem("reader-theme")
    if (stored === "dark" || stored === "light") setTheme(stored)
  }, [])

  return (
    <div className={theme === "dark" ? "bg-white/5 border border-white/10 rounded-2xl p-5 mb-6 text-white" : "bg-indigo-50 border border-indigo-100 rounded-2xl p-5 mb-6"}>
      <div className="flex items-center justify-between mb-3">
        <p className={theme === "dark" ? "text-xs font-medium text-indigo-300 uppercase tracking-wide" : "text-xs font-medium text-indigo-600 uppercase tracking-wide"}>
          Previously on... (Ch. {lastChapter})
        </p>
        <button onClick={onDismiss} className={theme === "dark" ? "text-gray-500 hover:text-white text-lg" : "text-indigo-300 hover:text-indigo-500 text-lg"}>×</button>
      </div>
      <p className={theme === "dark" ? "text-sm text-gray-100 leading-relaxed mb-4" : "text-sm text-gray-700 leading-relaxed mb-4"}>{recall}</p>
      <button onClick={onContinue}
        className="text-sm bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors">
        Continue Reading
      </button>
    </div>
  )
}
