"use client"

import { useEffect, useState } from "react"

import { monetizationApi } from "@/lib/api/monetization"
import { playRewardedAd } from "@/lib/monetization/rewardedAds"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { ResolveRewardedAdSessionResponse, RewardedAdStatus } from "@/types/monetization"

type RewardedAdPlacement = "points_wallet" | "daily_cap_prompt"

interface RewardedAdEarnCardProps {
  placement: RewardedAdPlacement
  compact?: boolean
  onRewardEarned?: (result: ResolveRewardedAdSessionResponse) => void
}

export function RewardedAdEarnCard({
  placement,
  compact = false,
  onRewardEarned,
}: RewardedAdEarnCardProps) {
  const user = useAuthStore((state) => state.user)
  const theme = usePreferencesStore((state) => state.theme)
  const isDark = theme === "dark"
  const [status, setStatus] = useState<RewardedAdStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!user) {
      setStatus(null)
      return
    }
    setLoading(true)
    monetizationApi
      .getRewardedAdStatus()
      .then((result) => setStatus(result))
      .catch(() => {
        setStatus({
          enabled: false,
          provider: "google_publisher_tag",
          reward_points: 0,
          daily_cap: 0,
          claims_used_today: 0,
          claims_remaining_today: 0,
          session_ttl_seconds: 0,
          min_grant_seconds: 0,
          reason: "We could not load rewarded-ad availability right now.",
        })
      })
      .finally(() => setLoading(false))
  }, [user])

  if (!user) {
    return null
  }

  const rewardPoints = status?.reward_points ?? 0
  const remaining = status?.claims_remaining_today ?? 0
  const available = Boolean(status?.enabled && remaining > 0)

  const handleStart = async () => {
    setActionBusy(true)
    setMessage(null)
    try {
      const session = await monetizationApi.startRewardedAdSession(placement)
      const playback = await playRewardedAd(session.ad_unit_path)
      const result = await monetizationApi.resolveRewardedAdSession({
        sessionToken: session.session_token,
        outcome: playback.outcome,
        rewardType: playback.rewardType ?? null,
        rewardAmount: playback.rewardAmount ?? null,
        errorMessage: playback.errorMessage ?? null,
      })
      setMessage(result.confirmation_message)
      setStatus((current) =>
        current
          ? {
              ...current,
              claims_used_today: Math.max(current.daily_cap - result.claims_remaining_today, 0),
              claims_remaining_today: result.claims_remaining_today,
            }
          : current
      )
      if (result.reward_points_granted > 0) {
        onRewardEarned?.(result)
      }
    } catch {
      setMessage("We could not start the rewarded ad right now.")
    } finally {
      setActionBusy(false)
    }
  }

  const shellClasses = compact
    ? isDark
      ? "mt-5 rounded-[1.4rem] border border-sky-400/20 bg-sky-400/8 p-5"
      : "mt-5 rounded-[1.4rem] border border-sky-200 bg-sky-50 p-5"
    : isDark
      ? "rounded-[1rem] border border-[rgba(var(--border),0.75)] bg-[rgba(255,255,255,0.03)] px-4 py-4"
      : "rounded-[1rem] border border-[rgba(var(--border),0.75)] bg-[rgba(255,255,255,0.55)] px-4 py-4"

  return (
    <div className={shellClasses}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>
        Rewarded points
      </p>
      <h3 className="mt-3 text-lg font-semibold text-[rgb(var(--foreground))]">
        Watch one ad, earn {loading ? "..." : rewardPoints} LoreVia points
      </h3>
      <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
        Watch one rewarded ad to earn a small, non-transferable point grant inside LoreVia. Skipping is okay and nothing is charged.
      </p>
      <p className={`mt-3 text-xs uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
        {loading
          ? "Checking availability..."
          : available
            ? `${remaining} of ${status?.daily_cap ?? 0} claims left today`
            : status?.reason ?? "No rewarded-ad claims left today"}
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleStart}
          disabled={loading || actionBusy || !available}
          className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {actionBusy ? "Opening ad..." : `Earn ${rewardPoints} points`}
        </button>
      </div>
      {message ? (
        <p className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{message}</p>
      ) : null}
    </div>
  )
}
