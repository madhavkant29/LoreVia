"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { RewardedAdEarnCard } from "@/components/monetization/RewardedAdEarnCard"
import { monetizationApi } from "@/lib/api/monetization"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import {
  DAILY_CAP_EVENT,
  type DailyCapEventDetail,
} from "@/lib/monetization/limitRecovery"
import type { PointSpendOffer, ResolveRewardedAdSessionResponse } from "@/types/monetization"

function actionCopy(action: DailyCapEventDetail["action"]): { title: string; body: string } {
  switch (action) {
    case "search":
      return {
        title: "You hit today's search cap",
        body: "Searches refresh tomorrow. You can upgrade for more headroom, or spend a few points for same-day overflow.",
      }
    case "prediction":
      return {
        title: "You hit today's question cap",
        body: "Prediction-style Q&A refreshes tomorrow. Upgrade for higher daily limits, or spend points for one extra turn today.",
      }
    case "high_cost_authoring":
      return {
        title: "You hit today's authoring cap",
        body: "Story Advisor and continuity turns refresh tomorrow. Upgrade for higher daily limits, or spend points for one more same-day turn.",
      }
    default:
      return {
        title: "You hit today's limit",
        body: "This cap refreshes tomorrow. Upgrade for more room, or use points if your current plan supports same-day overflow.",
      }
  }
}

export function DailyCapPrompt() {
  const router = useRouter()
  const user = useAuthStore((state) => state.user)
  const theme = usePreferencesStore((state) => state.theme)
  const isDark = theme === "dark"
  const [eventDetail, setEventDetail] = useState<DailyCapEventDetail | null>(null)
  const [offers, setOffers] = useState<PointSpendOffer[]>([])
  const [balance, setBalance] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [spending, setSpending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const handleDailyCap = (event: Event) => {
      if (!(event instanceof CustomEvent) || !user) {
        return
      }
      const detail = event.detail as DailyCapEventDetail
      setEventDetail(detail)
      setMessage(null)
      setLoading(true)
      Promise.all([
        monetizationApi.getPointsBalance(),
        monetizationApi.getPointOffers(),
      ])
        .then(([points, pointOffers]) => {
          setBalance(points.balance)
          setOffers(pointOffers.offers)
        })
        .catch(() => {
          setBalance(null)
          setOffers([])
          setMessage("We could not load point overflow options right now.")
        })
        .finally(() => setLoading(false))
    }

    window.addEventListener(DAILY_CAP_EVENT, handleDailyCap as EventListener)
    return () => window.removeEventListener(DAILY_CAP_EVENT, handleDailyCap as EventListener)
  }, [user])

  if (!eventDetail || !user) {
    return null
  }

  const copy = actionCopy(eventDetail.action)
  const matchingOffer = offers.find((offer) => offer.action === eventDetail.action) ?? null
  const canSpend = Boolean(
    matchingOffer &&
    matchingOffer.eligible &&
    typeof balance === "number" &&
    balance >= matchingOffer.points_cost
  )

  const close = () => {
    setEventDetail(null)
    setMessage(null)
  }

  const handleSpend = async () => {
    if (!matchingOffer) {
      return
    }
    setSpending(true)
    setMessage(null)
    try {
      const result = await monetizationApi.spendPoints(matchingOffer.code)
      setBalance(result.balance)
      setMessage(`${result.confirmation_message} Retry your action now.`)
    } catch {
      setMessage("We could not complete that point spend right now.")
    } finally {
      setSpending(false)
    }
  }

  const handleRewardEarned = (result: ResolveRewardedAdSessionResponse) => {
    setBalance(result.balance)
    setMessage(`${result.confirmation_message} You can spend those points from this prompt or from your wallet.`)
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/55 px-4 py-6 backdrop-blur-sm">
      <div
        className={`w-full max-w-xl rounded-[1.8rem] border p-6 shadow-[0_30px_80px_-24px_rgba(0,0,0,0.45)] ${
          isDark ? "border-white/10 bg-[#0b0f14] text-slate-100" : "border-stone-200 bg-[#fffaf2] text-stone-900"
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>
              Daily cap reached
            </p>
            <h2 className="mt-3 text-2xl font-semibold">{copy.title}</h2>
          </div>
          <button
            type="button"
            onClick={close}
            className={`rounded-full px-3 py-1 text-sm ${isDark ? "bg-white/8 text-slate-300" : "bg-stone-100 text-stone-500"}`}
          >
            Close
          </button>
        </div>

        <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{copy.body}</p>

        <div className={`mt-5 rounded-[1.2rem] border px-4 py-4 ${isDark ? "border-white/8 bg-white/[0.04]" : "border-stone-200 bg-white/80"}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Points balance</p>
              <p className="mt-2 text-2xl font-semibold">{loading ? "..." : `${balance ?? 0}`}</p>
            </div>
            <button
              type="button"
              onClick={() => {
                close()
                router.push("/settings#points-wallet")
              }}
              className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-100 text-stone-800"}`}
            >
              Open points wallet
            </button>
          </div>
        </div>

        {matchingOffer ? (
          <div className={`mt-5 rounded-[1.4rem] border p-5 ${isDark ? "border-emerald-400/20 bg-emerald-400/8" : "border-emerald-200 bg-emerald-50"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Same-day overflow</p>
            <h3 className="mt-3 text-lg font-semibold">{matchingOffer.title}</h3>
            <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{matchingOffer.description}</p>
            <p className={`mt-3 text-sm font-semibold ${isDark ? "text-emerald-200" : "text-emerald-800"}`}>
              Cost: {matchingOffer.points_cost} points
            </p>
            {!matchingOffer.eligible && matchingOffer.reason ? (
              <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{matchingOffer.reason}</p>
            ) : null}
            {matchingOffer.eligible && !canSpend ? (
              <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                You need at least {matchingOffer.points_cost} points to use this overflow option today.
              </p>
            ) : null}
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleSpend}
                disabled={!canSpend || spending}
                className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {spending ? "Spending points..." : `Spend ${matchingOffer.points_cost} points`}
              </button>
              <button
                type="button"
                onClick={() => {
                  close()
                  router.push("/upgrade")
                }}
                className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "border border-white/12 text-slate-100" : "border border-stone-200 text-stone-800"}`}
              >
                View pricing
              </button>
            </div>
          </div>
        ) : (
          <div className={`mt-5 rounded-[1.4rem] border p-5 ${isDark ? "border-white/8 bg-white/[0.04]" : "border-stone-200 bg-white/85"}`}>
            <p className="text-sm leading-7">
              This limit is best solved with a higher plan right now.
            </p>
            <button
              type="button"
              onClick={() => {
                close()
                router.push("/upgrade")
              }}
              className="mt-4 rounded-full bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-4 py-2 text-sm font-semibold text-white"
            >
              Go to pricing
            </button>
          </div>
        )}

        <RewardedAdEarnCard compact placement="daily_cap_prompt" onRewardEarned={handleRewardEarned} />

        {message ? (
          <div className={`mt-5 rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-indigo-400/20 bg-indigo-400/10 text-indigo-100" : "border-indigo-200 bg-indigo-50 text-indigo-700"}`}>
            {message}
          </div>
        ) : null}
      </div>
    </div>
  )
}
