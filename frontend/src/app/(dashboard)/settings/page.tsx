"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import {
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
} from "@/components/ui/Workspace"
import { RewardedAdEarnCard } from "@/components/monetization/RewardedAdEarnCard"
import { authApi } from "@/lib/api/auth"
import { billingApi } from "@/lib/api/billing"
import { monetizationApi } from "@/lib/api/monetization"
import { tierLabel } from "@/lib/billing/plans"
import { formatPointEntryLabel, formatPointsDelta } from "@/lib/monetization/formatters"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type {
  PointLedgerEntry,
  PointSpendOffer,
  ReferralSummary,
  ResolveRewardedAdSessionResponse,
} from "@/types/monetization"

const MODES = [
  { value: "casual", label: "Casual", desc: "Quick summaries and light-touch guidance." },
  { value: "analyst", label: "Analyst", desc: "Deeper context and richer breakdowns." },
  { value: "speed", label: "Speed", desc: "Minimal output for fast reading sessions." },
]

export default function SettingsPage() {
  const { user, setUser, logout } = useAuthStore()
  const { theme, setTheme } = usePreferencesStore()
  const [billingBusy, setBillingBusy] = useState(false)
  const [billingMessage, setBillingMessage] = useState<string | null>(null)
  const [goalDraft, setGoalDraft] = useState("1000")
  const [goalSaving, setGoalSaving] = useState(false)
  const [goalMessage, setGoalMessage] = useState<string | null>(null)
  const [pointsBalance, setPointsBalance] = useState<number>(0)
  const [pointsLedger, setPointsLedger] = useState<PointLedgerEntry[]>([])
  const [referralSummary, setReferralSummary] = useState<ReferralSummary | null>(null)
  const [pointOffers, setPointOffers] = useState<PointSpendOffer[]>([])
  const [pointsLoading, setPointsLoading] = useState(false)
  const [pointsMessage, setPointsMessage] = useState<string | null>(null)
  const [referralMessage, setReferralMessage] = useState<string | null>(null)
  const router = useRouter()
  const displayTier = user?.tier_label ?? tierLabel(user?.tier)
  const purchasedTier = tierLabel(user?.plan_tier)
  const trialEndsLabel = user?.trial_ends_at
    ? new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(user.trial_ends_at))
    : null

  const loadPointsWallet = () => {
    setPointsLoading(true)
    setPointsMessage(null)
    Promise.all([
      monetizationApi.getPointsBalance(),
      monetizationApi.getPointsLedger(),
      monetizationApi.getReferralSummary(),
      monetizationApi.getPointOffers(),
    ])
      .then(([balance, ledger, referral, offers]) => {
        setPointsBalance(balance.balance)
        setPointsLedger(ledger)
        setReferralSummary(referral)
        setPointOffers(offers.offers)
      })
      .catch(() => {
        setPointsMessage("We could not load your points wallet right now.")
      })
      .finally(() => setPointsLoading(false))
  }

  useEffect(() => {
    setGoalDraft(String(user?.daily_word_goal ?? 1000))
  }, [user?.daily_word_goal])

  useEffect(() => {
    if (!user) return
    loadPointsWallet()
  }, [user])

  const changeMode = async (mode: string) => {
    await authApi.setReadingMode(mode)
    if (user) setUser({ ...user, reading_mode: mode as "casual" | "analyst" | "speed" })
  }

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore logout errors
    }

    logout()
    router.replace("/login")
  }

  const openBillingPortal = async () => {
    setBillingBusy(true)
    setBillingMessage(null)
    try {
      const result = await billingApi.portal()
      if (!result.billing_enabled || !result.portal_url) {
        setBillingMessage(result.message ?? "Billing is not configured in this environment yet.")
        return
      }
      window.location.href = result.portal_url
    } catch {
      setBillingMessage("We could not open the billing portal right now. Please try again in a moment.")
    } finally {
      setBillingBusy(false)
    }
  }

  const saveDailyGoal = async () => {
    const parsedGoal = Math.max(1, Number(goalDraft) || 0)
    if (!parsedGoal) {
      setGoalMessage("Enter a daily word goal above zero.")
      return
    }

    setGoalSaving(true)
    setGoalMessage(null)
    try {
      const updated = await authApi.setDailyWordGoal(parsedGoal)
      setUser(updated)
      setGoalDraft(String(updated.daily_word_goal))
      setGoalMessage("Daily goal updated.")
    } catch {
      setGoalMessage("We could not save the daily goal right now.")
    } finally {
      setGoalSaving(false)
    }
  }

  const copyReferralLink = async () => {
    const referralUrl = referralSummary?.referral_url
    if (!referralUrl) {
      setReferralMessage("Referral link is not ready yet.")
      return
    }
    try {
      await navigator.clipboard.writeText(referralUrl)
      setReferralMessage("Referral link copied.")
    } catch {
      setReferralMessage("We could not copy the referral link right now.")
    }
  }

  const handleRewardEarned = (result: ResolveRewardedAdSessionResponse) => {
    setPointsBalance(result.balance)
    setPointsMessage(result.confirmation_message)
    loadPointsWallet()
  }

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="space-y-8 pb-12">
        <WorkspacePanel tone="strong" className="p-6 sm:p-8">
          <WorkspaceHeader
            eyebrow="Settings"
            title="Make LoreVia feel stable, personal, and low-friction."
            description="A professional settings page should keep high-impact controls obvious: account status, billing, appearance, reading mode, and a safe sign-out path."
            meta={
              <div className="flex flex-wrap justify-end gap-3">
                <div className="app-chip">{displayTier} plan</div>
                <div className="app-chip">{theme} theme</div>
              </div>
            }
          />
        </WorkspacePanel>

        <section className="grid gap-4 sm:grid-cols-3">
          <WorkspaceMetric
            label="Plan"
            value={displayTier}
            note={user?.trial_active ? "Temporary Author access during trial" : "Current workspace access level"}
            accent="accent"
          />
          <WorkspaceMetric
            label="Reading mode"
            value={(user?.reading_mode ?? "casual").toUpperCase()}
            note="Default answer depth"
          />
          <WorkspaceMetric
            label="Theme"
            value={theme.toUpperCase()}
            note="Synced with the reader"
            accent="success"
          />
        </section>

        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <WorkspacePanel className="p-6">
            <p className="app-eyebrow">Account</p>
            <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
              Billing and account details
            </h2>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="app-stat">
                <p className="app-stat__label">Email</p>
                <p className="mt-3 break-all text-base font-semibold text-[rgb(var(--foreground))]">
                  {user?.email ?? "No email available"}
                </p>
              </div>
              <div className="app-stat">
                <p className="app-stat__label">Plan status</p>
                <p className="mt-3 text-base font-semibold capitalize text-[rgb(var(--foreground))]">
                  {displayTier}
                </p>
              </div>
            </div>
            {user?.trial_active ? (
              <p className="mt-5 max-w-2xl rounded-[1.1rem] border border-emerald-300/30 bg-emerald-100/70 px-4 py-3 text-sm leading-7 text-emerald-950 dark:bg-emerald-300/10 dark:text-emerald-100">
                You are currently seeing Author (free trial). Your purchased plan is {purchasedTier}, so access will revert when the trial ends{trialEndsLabel ? ` on ${trialEndsLabel}` : ""} unless you upgrade.
              </p>
            ) : (
              <p className="mt-5 max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                Purchased plan: {purchasedTier}. Payment details and cancellations live in the billing portal.
              </p>
            )}
            <p className="mt-5 max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              Subscription changes still begin from pricing, while payment details and cancellations live in the billing portal.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <button onClick={openBillingPortal} disabled={billingBusy} className="app-button-primary disabled:opacity-60">
                {billingBusy ? "Opening billing..." : "Open billing portal"}
              </button>
            </div>
            {billingMessage ? (
              <div className="mt-4 rounded-[1.1rem] border border-amber-300/40 bg-amber-100/70 px-4 py-3 text-sm text-amber-900 dark:bg-amber-300/10 dark:text-amber-100">
                {billingMessage}
              </div>
            ) : null}
          </WorkspacePanel>

          <WorkspacePanel className="p-6">
            <p className="app-eyebrow">Appearance</p>
            <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
              Choose the workspace tone
            </h2>
            <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              Theme selection is synced automatically across the dashboard and the reader.
            </p>
            <div className="mt-5 grid gap-3">
              {[
                { value: "light", label: "Light", desc: "Warm paper surfaces and bright working cards." },
                { value: "dark", label: "Dark", desc: "Low-glare contrast for long sessions and deep reading." },
              ].map((option) => {
                const active = theme === option.value
                return (
                  <button
                    key={option.value}
                    onClick={() => setTheme(option.value as "light" | "dark")}
                    className={`rounded-[1.3rem] border p-4 text-left transition ${
                      active
                        ? "border-[rgba(var(--accent),0.3)] bg-[rgba(var(--accent),0.12)]"
                        : "border-[rgba(var(--border),0.8)] bg-[rgba(255,255,255,0.38)] hover:bg-[rgba(255,255,255,0.58)] dark:bg-[rgba(255,255,255,0.03)]"
                    }`}
                  >
                    <p className="text-sm font-semibold text-[rgb(var(--foreground))]">{option.label}</p>
                    <p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{option.desc}</p>
                  </button>
                )
              })}
            </div>
          </WorkspacePanel>
        </div>

        <WorkspacePanel className="p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="app-eyebrow">Answer style</p>
              <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                Set the default reading mode
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              This controls how much context LoreVia gives you by default, so the decision should feel explicit and easy to compare.
            </p>
          </div>

          <div className="mt-5 grid gap-3 lg:grid-cols-3">
            {MODES.map((mode) => {
              const active = user?.reading_mode === mode.value
              return (
                <button
                  key={mode.value}
                  onClick={() => changeMode(mode.value)}
                  className={`rounded-[1.3rem] border p-5 text-left transition ${
                    active
                      ? "border-[rgba(var(--accent),0.3)] bg-[rgba(var(--accent),0.12)]"
                      : "border-[rgba(var(--border),0.8)] bg-[rgba(255,255,255,0.38)] hover:bg-[rgba(255,255,255,0.58)] dark:bg-[rgba(255,255,255,0.03)]"
                  }`}
                >
                  <p className="text-sm font-semibold text-[rgb(var(--foreground))]">{mode.label}</p>
                  <p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{mode.desc}</p>
                </button>
              )
            })}
          </div>
        </WorkspacePanel>

        <WorkspacePanel className="p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="app-eyebrow">Daily goal</p>
              <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                Set your personal writing target
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              This goal feeds the overview page and tracks progress from manuscript saves across your workspace.
            </p>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
            <label className="app-stat">
              <p className="app-stat__label">Words per day</p>
              <input
                type="number"
                min={1}
                value={goalDraft}
                onChange={(event) => setGoalDraft(event.target.value)}
                className="mt-3 w-full rounded-[1rem] border border-[rgba(var(--border),0.8)] bg-[rgba(255,255,255,0.7)] px-4 py-3 text-base font-semibold text-[rgb(var(--foreground))] outline-none dark:bg-[rgba(255,255,255,0.04)]"
              />
            </label>
            <div className="app-stat">
              <p className="app-stat__label">Today</p>
              <p className="mt-3 text-base font-semibold text-[rgb(var(--foreground))]">
                {(user?.today_word_count ?? 0).toLocaleString()} / {(user?.daily_word_goal ?? 1000).toLocaleString()} words
              </p>
              <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                Progress updates when you save manuscript edits, and your streak is based on daily sign-ins.
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button onClick={saveDailyGoal} disabled={goalSaving} className="app-button-primary disabled:opacity-60">
                  {goalSaving ? "Saving..." : "Save daily goal"}
                </button>
                {goalMessage ? (
                  <span className="text-sm text-[rgb(var(--muted-foreground))]">{goalMessage}</span>
                ) : null}
              </div>
            </div>
          </div>
        </WorkspacePanel>

        <div id="points-wallet">
          <WorkspacePanel className="p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="app-eyebrow">Points wallet</p>
              <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                Track balance, referrals, and overflow relief
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              Points are supplemental only. They can soften a capped day, but they do not replace plan upgrades or unlock higher-tier author tools.
            </p>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            <div className="app-stat">
              <p className="app-stat__label">Current balance</p>
              <p className="mt-3 text-3xl font-semibold text-[rgb(var(--foreground))]">
                {pointsLoading ? "..." : pointsBalance.toLocaleString()}
              </p>
              <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                Earned from referrals and milestone rewards, then spent on same-day overflow when your plan already supports that action.
              </p>
            </div>
            <div className="app-stat">
              <p className="app-stat__label">Referral code</p>
              <p className="mt-3 break-all text-base font-semibold text-[rgb(var(--foreground))]">
                {pointsLoading ? "Loading..." : referralSummary?.referral_code ?? "Not available yet"}
              </p>
              <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                Invite a verified reader who actually processes a first book, and rewards are added automatically.
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <button onClick={copyReferralLink} className="app-button-primary disabled:opacity-60" disabled={pointsLoading || !referralSummary?.referral_url}>
                  Copy referral link
                </button>
                {referralMessage ? <span className="text-sm text-[rgb(var(--muted-foreground))]">{referralMessage}</span> : null}
              </div>
            </div>
            <div className="app-stat">
              <p className="app-stat__label">Referral rewards</p>
              <p className="mt-3 text-base font-semibold text-[rgb(var(--foreground))]">
                {(referralSummary?.rewards.length ?? 0).toLocaleString()} total
              </p>
              <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                Your wallet updates lazily on reads, so expirations and new grants stay accurate without a separate balance counter.
              </p>
            </div>
          </div>

          {pointsMessage ? (
            <div className="mt-4 rounded-[1.1rem] border border-amber-300/40 bg-amber-100/70 px-4 py-3 text-sm text-amber-900 dark:bg-amber-300/10 dark:text-amber-100">
              {pointsMessage}
            </div>
          ) : null}

          <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-4">
              <div className="app-stat">
                <p className="app-stat__label">Recent ledger activity</p>
                <div className="mt-4 space-y-3">
                  {pointsLedger.slice(0, 6).map((entry) => (
                    <div key={entry.id} className="rounded-[1rem] border border-[rgba(var(--border),0.75)] bg-[rgba(255,255,255,0.55)] px-4 py-3 dark:bg-[rgba(255,255,255,0.03)]">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-[rgb(var(--foreground))]">{formatPointEntryLabel(entry)}</p>
                          <p className="mt-1 text-xs text-[rgb(var(--muted-foreground))]">
                            {new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(entry.created_at))}
                          </p>
                        </div>
                        <p className={`text-sm font-semibold ${entry.points_delta >= 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>
                          {formatPointsDelta(entry.points_delta)} pts
                        </p>
                      </div>
                    </div>
                  ))}
                  {!pointsLoading && pointsLedger.length === 0 ? (
                    <p className="text-sm text-[rgb(var(--muted-foreground))]">
                      No point activity yet. Your first processed book and qualified referrals will start the ledger.
                    </p>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <RewardedAdEarnCard placement="points_wallet" onRewardEarned={handleRewardEarned} />
              <div className="app-stat">
                <p className="app-stat__label">Overflow options</p>
                <div className="mt-4 space-y-3">
                  {pointOffers.map((offer) => (
                    <div key={offer.code} className="rounded-[1rem] border border-[rgba(var(--border),0.75)] bg-[rgba(255,255,255,0.55)] px-4 py-4 dark:bg-[rgba(255,255,255,0.03)]">
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
                </div>
              </div>
            </div>
          </div>
          </WorkspacePanel>
        </div>

        <div className="flex justify-start">
          <button
            onClick={handleLogout}
            className="rounded-2xl px-4 py-3 text-sm font-semibold text-rose-600 transition hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-500/10"
          >
            Sign out
          </button>
        </div>
      </div>
    </WorkspacePage>
  )
}
