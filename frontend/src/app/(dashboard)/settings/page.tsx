"use client"

import React, { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import {
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
} from "@/components/ui/Workspace"
import { authApi } from "@/lib/api/auth"
import { billingApi } from "@/lib/api/billing"
import { tierLabel } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

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
  const [usernameDraft, setUsernameDraft] = useState("")
  const [usernameSaving, setUsernameSaving] = useState(false)
  const [usernameMessage, setUsernameMessage] = useState<string | null>(null)
  const [permissionSaving, setPermissionSaving] = useState(false)
  const [permissionMessage, setPermissionMessage] = useState<string | null>(null)
  const router = useRouter()
  const displayTier = user?.tier_label ?? tierLabel(user?.tier)
  const purchasedTier = tierLabel(user?.plan_tier)
  const trialEndsLabel = user?.trial_ends_at
    ? new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(user.trial_ends_at))
    : null

  useEffect(() => {
    setGoalDraft(String(user?.daily_word_goal ?? 1000))
  }, [user?.daily_word_goal])

  useEffect(() => {
    setUsernameDraft(user?.username ?? "")
  }, [user?.username])

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

  const saveUsername = async () => {
    const trimmedUsername = usernameDraft.trim()
    if (!trimmedUsername) {
      setUsernameMessage("Enter a username to keep your public LoreVia identity active.")
      return
    }

    setUsernameSaving(true)
    setUsernameMessage(null)
    try {
      const updated = await authApi.setUsername(trimmedUsername)
      setUser(updated)
      setUsernameDraft(updated.username ?? "")
      setUsernameMessage(user?.username ? "Public username updated." : "Public username saved.")
    } catch {
      setUsernameMessage("We could not save that username. Try a different handle with letters, numbers, hyphens, or underscores.")
    } finally {
      setUsernameSaving(false)
    }
  }

  const changeMessagingPermission = async (messagingPermission: "anyone" | "friends_only") => {
    setPermissionSaving(true)
    setPermissionMessage(null)
    try {
      const updated = await authApi.setMessagingPermission(messagingPermission)
      setUser(updated)
      setPermissionMessage("Messaging privacy updated.")
    } catch {
      setPermissionMessage("We could not save your messaging privacy right now.")
    } finally {
      setPermissionSaving(false)
    }
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
            note="Synced with the reading workspace"
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
                Purchased plan: {purchasedTier}. Canceling, payment method changes, and invoice access live in the billing portal.
              </p>
            )}
            <p className="mt-5 max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              Use the billing portal when you need to cancel renewal, update payment details, or download invoices. Subscription upgrades still begin from pricing.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <button onClick={openBillingPortal} disabled={billingBusy} className="app-button-primary disabled:opacity-60">
                {billingBusy ? "Opening billing..." : "Manage billing / cancel subscription"}
              </button>
            </div>
            {billingMessage ? (
              <div className="mt-4 rounded-[1.1rem] border border-amber-300/40 bg-amber-100/70 px-4 py-3 text-sm text-amber-900 dark:bg-amber-300/10 dark:text-amber-100">
                {billingMessage}
              </div>
            ) : null}
          </WorkspacePanel>

          <WorkspacePanel className="p-6">
            <p className="app-eyebrow">Public identity</p>
            <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
              Choose the username people see on LoreVia
            </h2>
            <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              This is your public <span className="font-semibold">@username</span> for profiles, forum posts, and chats. It is separate from the author or pen name you put on each manuscript.
            </p>
            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
              <label className="app-stat">
                <p className="app-stat__label">Public username</p>
                <input
                  type="text"
                  minLength={3}
                  maxLength={32}
                  autoComplete="username"
                  value={usernameDraft}
                  onChange={(event) => setUsernameDraft(event.target.value)}
                  className="mt-3 w-full rounded-[1rem] border border-[rgba(var(--border),0.8)] bg-[rgba(255,255,255,0.7)] px-4 py-3 text-base font-semibold text-[rgb(var(--foreground))] outline-none dark:bg-[rgba(255,255,255,0.04)]"
                />
              </label>
              <div className="app-stat">
                <p className="app-stat__label">Current public handle</p>
                <p className="mt-3 text-base font-semibold text-[rgb(var(--foreground))]">
                  {user?.username ? `@${user.username}` : "No username set yet"}
                </p>
                <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                  New author uploads default to this username, but you can change the manuscript author or pen name for any individual book without changing your account handle.
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    onClick={saveUsername}
                    disabled={usernameSaving || usernameDraft.trim().length < 3}
                    className="app-button-primary disabled:opacity-60"
                  >
                    {usernameSaving ? "Saving..." : user?.username ? "Change username" : "Save username"}
                  </button>
                  {usernameMessage ? (
                    <span className="text-sm text-[rgb(var(--muted-foreground))]">{usernameMessage}</span>
                  ) : null}
                </div>
              </div>
            </div>
          </WorkspacePanel>

          <WorkspacePanel className="p-6">
            <p className="app-eyebrow">Appearance</p>
            <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
              Choose the workspace tone
            </h2>
            <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              Theme selection is synced automatically across the dashboard and the reading workspace.
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
              <p className="app-eyebrow">Messaging privacy</p>
              <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                Control who can start a direct message
              </h2>
            </div>
            <p className="max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
              Choose whether anyone can message you, or whether new chats should unlock only after a friend request is accepted from notifications.
            </p>
          </div>

          <div className="mt-5 grid gap-3 lg:grid-cols-2">
            {[
              { value: "anyone" as const, label: "Anyone can message me", desc: "People can open a chat immediately from search, forum, or profile entrypoints." },
              { value: "friends_only" as const, label: "Friends only", desc: "People must send a friend request first, and you accept it from notifications." },
            ].map((option) => {
              const active = (user?.messaging_permission ?? "anyone") === option.value
              return (
                <button
                  key={option.value}
                  onClick={() => void changeMessagingPermission(option.value)}
                  disabled={permissionSaving}
                  className={`rounded-[1.3rem] border p-5 text-left transition ${active ? "border-[rgba(var(--accent),0.3)] bg-[rgba(var(--accent),0.12)]" : "border-[rgba(var(--border),0.8)] bg-[rgba(255,255,255,0.38)] hover:bg-[rgba(255,255,255,0.58)] dark:bg-[rgba(255,255,255,0.03)]"}`}
                >
                  <p className="text-sm font-semibold text-[rgb(var(--foreground))]">{option.label}</p>
                  <p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">{option.desc}</p>
                </button>
              )
            })}
          </div>
          {permissionMessage ? (
            <p className="mt-4 text-sm text-[rgb(var(--muted-foreground))]">{permissionMessage}</p>
          ) : null}
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
