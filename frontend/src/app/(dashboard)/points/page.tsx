"use client"

import { useCallback, useEffect, useMemo, useState } from "react"

import { RewardedAdEarnCard } from "@/components/monetization/RewardedAdEarnCard"
import {
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
} from "@/components/ui/Workspace"
import { monetizationApi } from "@/lib/api/monetization"
import { formatPointEntryLabel, formatPointsDelta } from "@/lib/monetization/formatters"
import { useAuthStore } from "@/lib/stores/authStore"
import type {
  PointLedgerEntry,
  PointSpendOffer,
  ReferralSummary,
  ResolveRewardedAdSessionResponse,
  RewardedAdStatus,
} from "@/types/monetization"

const ledgerDateFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
})

function clampDailyCap(value: number | undefined) {
  return Math.max(value ?? 3, 0)
}

function buildAdSlots(dailyCap: number, usedToday: number) {
  return Array.from({ length: dailyCap }, (_, index) => ({
    index,
    watched: index < usedToday,
  }))
}

export default function PointsPage() {
  const user = useAuthStore((state) => state.user)
  const [pointsBalance, setPointsBalance] = useState(0)
  const [pointsLedger, setPointsLedger] = useState<PointLedgerEntry[]>([])
  const [referralSummary, setReferralSummary] = useState<ReferralSummary | null>(null)
  const [pointOffers, setPointOffers] = useState<PointSpendOffer[]>([])
  const [adStatus, setAdStatus] = useState<RewardedAdStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const loadPointsPage = useCallback(() => {
    if (!user) {
      return
    }

    setLoading(true)
    setMessage(null)
    Promise.all([
      monetizationApi.getPointsBalance(),
      monetizationApi.getPointsLedger(),
      monetizationApi.getReferralSummary(),
      monetizationApi.getPointOffers(),
      monetizationApi.getRewardedAdStatus(),
    ])
      .then(([balance, ledger, referral, offers, rewardedAds]) => {
        setPointsBalance(balance.balance)
        setPointsLedger(ledger)
        setReferralSummary(referral)
        setPointOffers(offers.offers)
        setAdStatus(rewardedAds)
      })
      .catch(() => {
        setMessage("We could not load your points wallet right now.")
      })
      .finally(() => setLoading(false))
  }, [user])

  useEffect(() => {
    if (!user) {
      return
    }
    loadPointsPage()
  }, [loadPointsPage, user])

  const dailyCap = clampDailyCap(adStatus?.daily_cap)
  const usedToday = Math.min(adStatus?.claims_used_today ?? 0, dailyCap)
  const remainingToday = Math.max(adStatus?.claims_remaining_today ?? dailyCap, 0)
  const adSlots = useMemo(() => buildAdSlots(dailyCap, usedToday), [dailyCap, usedToday])

  const handleRewardEarned = (result: ResolveRewardedAdSessionResponse) => {
    setPointsBalance(result.balance)
    setMessage(result.confirmation_message)
    loadPointsPage()
  }

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="space-y-8 pb-12">
        <WorkspacePanel tone="strong" className="p-6 sm:p-8">
          <WorkspaceHeader
            eyebrow="Points"
            title="Points wallet"
            description="Track public-share costs, daily login rewards, upload rewards, beta read rewards, review rewards, and the daily rewarded-ad allowance from one place."
            meta={
              <div className="flex flex-wrap justify-end gap-3">
                <div className="app-chip">{loading ? "Syncing" : `${pointsBalance.toLocaleString()} points`}</div>
                <div className="app-chip">{remainingToday.toLocaleString()} ads left today</div>
              </div>
            }
          />
        </WorkspacePanel>

        <section className="grid gap-4 md:grid-cols-3">
          <WorkspaceMetric
            label="Current balance"
            value={loading ? "..." : pointsBalance.toLocaleString()}
            note="Non-transferable points available inside LoreVia"
            accent="accent"
          />
          <WorkspaceMetric
            label="Referral rewards"
            value={(referralSummary?.rewards.length ?? 0).toLocaleString()}
            note={referralSummary?.referral_code ? `Code ${referralSummary.referral_code}` : "Referral code not ready yet"}
            accent="success"
          />
          <WorkspaceMetric
            label="Ads left today"
            value={`${remainingToday.toLocaleString()} / ${dailyCap.toLocaleString()}`}
            note="The counter resets with the daily rewarded-ad window"
            accent="warning"
          />
        </section>

        {message ? (
          <div className="rounded-[1.1rem] border border-amber-300/40 bg-amber-100/70 px-4 py-3 text-sm text-amber-900 dark:bg-amber-300/10 dark:text-amber-100">
            {message}
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <WorkspacePanel className="p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="app-eyebrow">Ledger</p>
                <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                  Recent point activity
                </h2>
              </div>
              <p className="max-w-xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                Daily logins, first upload rewards, beta read rewards, review rewards, public sharing costs, referrals, expirations, and overflow spends appear here as the wallet changes.
              </p>
            </div>

            <div className="mt-5 space-y-3">
              {pointsLedger.slice(0, 8).map((entry) => (
                <div
                  key={entry.id}
                  className="rounded-[1rem] border border-[rgba(var(--border),0.75)] bg-[rgba(255,255,255,0.55)] px-4 py-3 dark:bg-[rgba(255,255,255,0.03)]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-[rgb(var(--foreground))]">
                        {formatPointEntryLabel(entry)}
                      </p>
                      <p className="mt-1 text-xs text-[rgb(var(--muted-foreground))]">
                        {ledgerDateFormatter.format(new Date(entry.created_at))}
                      </p>
                    </div>
                    <p className={`text-sm font-semibold ${entry.points_delta >= 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>
                      {formatPointsDelta(entry.points_delta)} pts
                    </p>
                  </div>
                </div>
              ))}
              {!loading && pointsLedger.length === 0 ? (
                <p className="text-sm text-[rgb(var(--muted-foreground))]">
                  No point activity yet. Daily logins, your first upload, beta read reviews, referrals, and rewarded ads will start the ledger.
                </p>
              ) : null}
            </div>
          </WorkspacePanel>

          <div className="space-y-6">
            <WorkspacePanel className="p-6">
              <p className="app-eyebrow">Referral</p>
              <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                Invite code
              </h2>
              <p className="mt-4 break-all text-base font-semibold text-[rgb(var(--foreground))]">
                {loading ? "Loading..." : referralSummary?.referral_code ?? "Not available yet"}
              </p>
              <p className="mt-3 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                Rewards are added automatically when a referred reader qualifies through the backend.
              </p>
            </WorkspacePanel>

            <WorkspacePanel className="p-6">
              <p className="app-eyebrow">Overflow options</p>
              <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                Spend points
              </h2>
              <div className="mt-5 space-y-3">
                {pointOffers.map((offer) => (
                  <div
                    key={offer.code}
                    className="rounded-[1rem] border border-[rgba(var(--border),0.75)] bg-[rgba(255,255,255,0.55)] px-4 py-4 dark:bg-[rgba(255,255,255,0.03)]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[rgb(var(--foreground))]">{offer.title}</p>
                        <p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{offer.description}</p>
                      </div>
                      <span className="rounded-full bg-[rgba(var(--accent),0.12)] px-3 py-1 text-xs font-semibold text-[rgb(var(--accent))]">
                        {offer.points_cost} pts
                      </span>
                    </div>
                    <p className="mt-3 text-xs uppercase tracking-[0.22em] text-[rgb(var(--muted-foreground))]">
                      {offer.eligible ? "Available on your plan" : offer.reason ?? "Upgrade required"}
                    </p>
                  </div>
                ))}
                {!loading && pointOffers.length === 0 ? (
                  <p className="text-sm text-[rgb(var(--muted-foreground))]">
                    No point-spend options are available for this account yet.
                  </p>
                ) : null}
              </div>
            </WorkspacePanel>
          </div>
        </div>

        <WorkspacePanel className="p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="app-eyebrow">Daily ad counter</p>
              <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                {remainingToday.toLocaleString()} ads left today
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              You can watch up to {dailyCap.toLocaleString()} rewarded ads per day. Each rewarded ad decreases this counter for the day.
            </p>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {adSlots.map((slot) => (
              <div
                key={slot.index}
                className={`rounded-[1rem] border px-4 py-4 ${
                  slot.watched
                    ? "border-emerald-300/40 bg-emerald-100/70 dark:bg-emerald-300/10"
                    : "border-[rgba(var(--border),0.75)] bg-[rgba(255,255,255,0.55)] dark:bg-[rgba(255,255,255,0.03)]"
                }`}
              >
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[rgb(var(--muted-foreground))]">
                  Ad {slot.index + 1}
                </p>
                <p className="mt-3 text-base font-semibold text-[rgb(var(--foreground))]">
                  {slot.watched ? "Watched" : "Available"}
                </p>
              </div>
            ))}
          </div>

          {adStatus?.enabled === false ? (
            <p className="mt-4 text-sm text-[rgb(var(--muted-foreground))]">
              {adStatus.reason ?? "Rewarded ads are not available right now."}
            </p>
          ) : null}

          <RewardedAdEarnCard placement="points_wallet" onRewardEarned={handleRewardEarned} />
        </WorkspacePanel>
      </div>
    </WorkspacePage>
  )
}
