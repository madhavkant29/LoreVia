"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import {
  DAILY_CAP_EVENT,
  DAILY_LIMIT_MESSAGE,
  type DailyCapEventDetail,
} from "@/lib/limits/dailyCap"

function actionCopy(action: DailyCapEventDetail["action"]): { title: string; body: string } {
  switch (action) {
    case "search":
      return {
        title: "You hit today's search cap",
        body: "Searches refresh tomorrow. Upgrade for more room if you need heavier same-day research.",
      }
    case "prediction":
      return {
        title: "You hit today's question cap",
        body: "Question turns refresh tomorrow. Upgrade for higher daily limits when this becomes part of your regular workflow.",
      }
    case "high_cost_authoring":
      return {
        title: "You hit today's authoring cap",
        body: "Story Advisor and continuity turns refresh tomorrow. Upgrade when you need deeper revision sessions in a single day.",
      }
    default:
      return {
        title: "You hit today's limit",
        body: "This limit refreshes tomorrow. Upgrade for more capacity if you need more room in the current plan cycle.",
      }
  }
}

export function DailyCapPrompt() {
  const router = useRouter()
  const user = useAuthStore((state) => state.user)
  const theme = usePreferencesStore((state) => state.theme)
  const isDark = theme === "dark"
  const [eventDetail, setEventDetail] = useState<DailyCapEventDetail | null>(null)

  useEffect(() => {
    const handleDailyCap = (event: Event) => {
      if (!(event instanceof CustomEvent) || !user) {
        return
      }
      setEventDetail(event.detail as DailyCapEventDetail)
    }

    window.addEventListener(DAILY_CAP_EVENT, handleDailyCap as EventListener)
    return () => window.removeEventListener(DAILY_CAP_EVENT, handleDailyCap as EventListener)
  }, [user])

  if (!eventDetail || !user) {
    return null
  }

  const copy = actionCopy(eventDetail.action)
  const bodyText =
    eventDetail.detail && eventDetail.detail !== DAILY_LIMIT_MESSAGE
      ? eventDetail.detail
      : copy.body

  const close = () => {
    setEventDetail(null)
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 px-4 py-6">
      <div
        className={`w-full max-w-xl rounded-lg border p-6 ${
          isDark ? "border-white/10 bg-[#0b0f14] text-slate-100" : "border-stone-200 bg-[#fffaf2] text-stone-900"
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>
              Daily cap reached
            </p>
            <h2 className="mt-3 text-2xl font-semibold">{copy.title}</h2>
          </div>
          <button
            type="button"
            onClick={close}
            className={`rounded-full px-3 py-1 text-sm ${isDark ? "bg-white/[0.08] text-slate-300" : "bg-stone-100 text-stone-500"}`}
          >
            Close
          </button>
        </div>

        <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{bodyText}</p>

        <div className={`mt-5 rounded-lg border p-5 ${isDark ? "border-white/[0.08] bg-white/[0.04]" : "border-stone-200 bg-white/85"}`}>
          <p className="text-sm leading-7">
            Paid plans are the only upgrade path exposed in the main author workspace.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                close()
                router.push("/upgrade")
              }}
              className="rounded-md bg-violet-700 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-600"
            >
              View pricing
            </button>
            <button
              type="button"
              onClick={close}
              className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "border border-white/[0.12] text-slate-100" : "border border-stone-200 text-stone-800"}`}
            >
              Continue later
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
