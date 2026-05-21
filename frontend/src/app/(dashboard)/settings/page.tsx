"use client"

import React, { useEffect, useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"

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
  const authHydrated = useAuthStore((state) => state.hydrated)
  const { theme, setTheme } = usePreferencesStore()
  const isDark = theme === "dark"
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
  const stableUser = authHydrated ? user : null
  const displayTier = stableUser?.tier_label ?? tierLabel(stableUser?.tier)
  const purchasedTier = tierLabel(stableUser?.plan_tier)
  const trialEndsLabel = stableUser?.trial_ends_at
    ? new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(stableUser.trial_ends_at))
    : null

  useEffect(() => {
    setGoalDraft(String(stableUser?.daily_word_goal ?? 1000))
  }, [stableUser?.daily_word_goal])

  useEffect(() => {
    setUsernameDraft(stableUser?.username ?? "")
  }, [stableUser?.username])

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

  const dailyGoal = stableUser?.daily_word_goal ?? 1000
  const todayWords = stableUser?.today_word_count ?? 0
  const goalProgress = Math.max(0, Math.min(100, Math.round((todayWords / Math.max(dailyGoal, 1)) * 100)))

  const summaryCards = [
    {
      label: "Plan",
      value: displayTier,
      note: stableUser?.trial_active ? "Temporary Author access during trial" : "Current workspace access level",
      icon: <PlanIcon />,
    },
    {
      label: "Reading mode",
      value: modeLabel(stableUser?.reading_mode ?? "casual"),
      note: "Default answer depth",
      icon: <ReadingIcon />,
    },
    {
      label: "Theme",
      value: theme === "dark" ? "Dark" : "Light",
      note: "Synced with workspace",
      icon: <ThemeIcon dark={isDark} />,
    },
  ]

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#0d1318] text-slate-100" : "bg-[#f4f5f7] text-stone-950"}`}>
      <div className="mx-auto max-w-[1220px] px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-5 pb-12">
          <section className={`overflow-hidden rounded-[1.55rem] border-2 ${isDark ? "border-slate-700/70 bg-[#11171d]" : "border-slate-200 bg-[#fcfcfb]"}`}>
            <div className="px-6 py-8 sm:px-8 sm:py-10 lg:px-12 lg:py-12">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-[#6fc7b3]" : "text-[#1f615d]"}`}>Settings</p>
              <h1 className={`mt-4 max-w-[780px] font-display text-[2.85rem] leading-[0.96] tracking-[-0.06em] ${isDark ? "text-[#f2ece3]" : "text-stone-950"} sm:text-[4.1rem]`}>
                Make LoreVia feel stable,
                <br className="hidden sm:block" />
                personal, and low-friction.
              </h1>
              <p className={`mt-5 max-w-[720px] text-[1.02rem] leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                A professional settings hub for the controls that matter: account, reading, appearance, privacy, and daily writing goals.
              </p>
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-3">
            {summaryCards.map((card) => (
              <SummaryCard key={card.label} isDark={isDark} icon={card.icon} label={card.label} value={card.value} note={card.note} />
            ))}
          </section>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SettingsCard
              isDark={isDark}
              icon={<BillingIcon />}
              eyebrow="Account"
              title="Billing and account details"
              description="Manage your payment details, invoices, and subscription."
              stacked
            >
              <div className="min-w-0 space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <InfoItem isDark={isDark} label="Email" value={stableUser?.email ?? "No email available"} />
                  <InfoItem isDark={isDark} label="Plan status" value={displayTier} />
                </div>
                <div className={`min-w-0 overflow-hidden rounded-[1rem] border-2 p-4 ${isDark ? "border-slate-700/70 bg-[#121921]" : "border-slate-200 bg-[#fbfcfd]"}`}>
                  {stableUser?.trial_active ? (
                    <p className={`max-w-2xl break-words text-sm leading-6 [overflow-wrap:anywhere] ${isDark ? "text-emerald-100" : "text-emerald-900"}`}>
                      You are currently seeing Author (free trial). Your purchased plan is {purchasedTier}, so access will revert when the trial ends{trialEndsLabel ? ` on ${trialEndsLabel}` : ""} unless you upgrade.
                    </p>
                  ) : (
                    <p className={`max-w-2xl break-words text-sm leading-6 [overflow-wrap:anywhere] ${isDark ? "text-slate-300" : "text-stone-700"}`}>
                      Purchased plan: {purchasedTier}. cancel renewal, payment method changes, and invoice access live in the billing portal.
                    </p>
                  )}
                  <p className={`mt-4 max-w-2xl break-words text-sm leading-6 [overflow-wrap:anywhere] ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                    Open the billing portal to manage your subscription, invoices, payment method, or cancellation.
                  </p>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button onClick={openBillingPortal} disabled={billingBusy} className={`${primaryActionClass(isDark, true)} shrink-0`}>
                      {billingBusy ? "Opening billing..." : "Manage billing / cancel subscription"}
                    </button>
                  </div>
                  {billingMessage ? <InlineMessage isDark={isDark} message={billingMessage} tone="warning" className="mt-4" /> : null}
                </div>
              </div>
            </SettingsCard>

            <SettingsCard
              isDark={isDark}
              icon={<IdentityIcon />}
              eyebrow="Public identity"
              title="Choose the username people see on LoreVia"
              stacked
              description={
                <>
                  This is your public <span className="font-semibold">@username</span> for profiles, forum posts, and chats. It is separate from the author or pen name you put on each manuscript.
                </>
              }
            >
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
                <div className="min-w-0 space-y-3">
                  <label className="block">
                    <span className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Public username</span>
                    <div className={`mt-3 flex min-w-0 items-center gap-3 overflow-hidden rounded-[1rem] border-2 px-4 py-3 ${isDark ? "border-slate-700/70 bg-[#121921]" : "border-slate-200 bg-white"}`}>
                      <input
                        type="text"
                        minLength={3}
                        maxLength={32}
                        autoComplete="username"
                        value={usernameDraft}
                        onChange={(event) => setUsernameDraft(event.target.value)}
                        onInput={(event) => setUsernameDraft((event.target as HTMLInputElement).value)}
                        className={`min-w-0 w-full bg-transparent text-base font-semibold outline-none ${isDark ? "text-white placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"}`}
                        placeholder="Choose a public username"
                      />
                      <span className={`${usernameDraft.trim().length >= 3 ? (isDark ? "text-[#6fc7b3]" : "text-[#1f615d]") : "text-slate-400"}`}>
                        <CheckCircleIcon />
                      </span>
                    </div>
                  </label>
                  {usernameMessage ? <InlineMessage isDark={isDark} message={usernameMessage} tone="neutral" /> : null}
                </div>

                <div className={`min-w-0 overflow-hidden rounded-[1rem] border-2 p-4 ${isDark ? "border-slate-700/70 bg-[#121921]" : "border-slate-200 bg-[#fbfcfd]"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Current public handle</p>
                  <p className={`mt-4 truncate text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>
                    {stableUser?.username ? `@${stableUser.username}` : "No username set yet"}
                  </p>
                  <p className={`mt-3 break-words text-sm leading-6 [overflow-wrap:anywhere] ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                    New author uploads default to this username, but you can change the manuscript author or pen name for any individual book without changing your account handle.
                  </p>
                  <button
                    onClick={saveUsername}
                    disabled={usernameSaving || usernameDraft.trim().length < 3}
                    className={`${primaryActionClass(isDark, false)} mt-5 w-full sm:w-auto`}
                  >
                    {usernameSaving ? "Saving..." : stableUser?.username ? "Change username" : "Save username"}
                  </button>
                </div>
              </div>
            </SettingsCard>
          </div>

          <SettingsCard
            isDark={isDark}
            icon={<AppearanceIcon />}
            eyebrow="Appearance"
            title="Choose the workspace tone"
            description="Theme selection is synced automatically across the dashboard and the reading workspace."
          >
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {[
                { value: "light", label: "Light", desc: "Warm paper surfaces and bright working cards.", icon: <SunIcon /> },
                { value: "dark", label: "Dark", desc: "Low-glare contrast for long sessions and deep reading.", icon: <MoonIcon /> },
              ].map((option) => {
                const active = theme === option.value
                return (
                  <SelectableCard
                    key={option.value}
                    isDark={isDark}
                    active={active}
                    title={option.label}
                    description={option.desc}
                    icon={option.icon}
                    onClick={() => setTheme(option.value as "light" | "dark")}
                  />
                )
              })}
            </div>
          </SettingsCard>

          <SettingsCard
            isDark={isDark}
            icon={<AnswerStyleIcon />}
            eyebrow="Answer style"
            title="Set the default reading mode"
            description="Set the default reading mode for answers and insights."
            sideNote="This controls how much context LoreVia gives you by default, so the decision should feel explicit and easy to compare."
          >
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
              {MODES.map((mode) => {
                const active = stableUser?.reading_mode === mode.value
                return (
                  <SelectableCard
                    key={mode.value}
                    isDark={isDark}
                    active={active}
                    title={mode.label}
                    description={mode.desc}
                    icon={mode.value === "casual" ? <ChatIcon /> : mode.value === "analyst" ? <BarsIcon /> : <BoltIcon />}
                    onClick={() => changeMode(mode.value)}
                  />
                )
              })}
            </div>
          </SettingsCard>

          <SettingsCard
            isDark={isDark}
            icon={<PrivacyIcon />}
            eyebrow="Messaging privacy"
            title="Control who can start a direct message"
            description="Control who can start a direct message."
            sideNote="Choose whether anyone can message you, or whether new chats should unlock only after a friend request is accepted."
          >
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {[
                { value: "anyone" as const, label: "Anyone can message me", desc: "People can open a chat immediately from search, forum, or profile entrypoints." },
                { value: "friends_only" as const, label: "Friends only", desc: "People must send a friend request first, and you accept it from notifications." },
              ].map((option) => {
                const active = (stableUser?.messaging_permission ?? "anyone") === option.value
                return (
                  <SelectableCard
                    key={option.value}
                    isDark={isDark}
                    active={active}
                    title={option.label}
                    description={option.desc}
                    icon={option.value === "anyone" ? <GlobeIcon /> : <FriendsIcon />}
                    disabled={permissionSaving}
                    onClick={() => void changeMessagingPermission(option.value)}
                  />
                )
              })}
            </div>
            {permissionMessage ? <InlineMessage isDark={isDark} message={permissionMessage} tone="neutral" className="mt-4" /> : null}
          </SettingsCard>

          <SettingsCard
            isDark={isDark}
            icon={<GoalIcon />}
            eyebrow="Daily goal"
            title="Set your personal writing target"
            description="Set your personal writing target."
            sideNote="This goal feeds the overview page and tracks progress from manuscript saves across your workspace."
          >
            <div className="grid grid-cols-1 gap-3 2xl:grid-cols-[240px_minmax(0,1fr)_180px]">
              <label className={`min-w-0 overflow-hidden rounded-[1.15rem] border-2 p-4 ${isDark ? "border-slate-700/70 bg-[#121921]" : "border-slate-200 bg-[#fbfcfd]"}`}>
                <span className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Words per day</span>
                <input
                  type="number"
                  min={1}
                  value={goalDraft}
                  onChange={(event) => setGoalDraft(event.target.value)}
                  className={`mt-3 w-full rounded-[0.95rem] border px-4 py-3 text-base font-semibold outline-none ${isDark ? "border-white/[0.12] bg-[#0f151c] text-white" : "border-[#d6dce3] bg-white text-stone-900"}`}
                />
                <button onClick={saveDailyGoal} disabled={goalSaving} className={`${primaryActionClass(isDark, false)} mt-4`}>
                  {goalSaving ? "Saving..." : "Save daily goal"}
                </button>
              </label>

              <div className={`min-w-0 overflow-hidden rounded-[1.15rem] border-2 p-4 ${isDark ? "border-slate-700/70 bg-[#121921]" : "border-slate-200 bg-[#fbfcfd]"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Today</p>
                <p className={`mt-3 text-[1.8rem] font-semibold tracking-[-0.03em] ${isDark ? "text-white" : "text-stone-950"}`}>
                  {todayWords.toLocaleString()} / {dailyGoal.toLocaleString()} words
                </p>
                <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                  Progress updates when you save manuscript edits, and your streak is based on daily sign-ins.
                </p>
                {goalMessage ? <InlineMessage isDark={isDark} message={goalMessage} tone="neutral" className="mt-4" /> : null}
              </div>

              <div className={`min-w-0 overflow-hidden flex flex-col items-center justify-center rounded-[1.15rem] border-2 p-4 ${isDark ? "border-slate-700/70 bg-[#121921]" : "border-slate-200 bg-[#fbfcfd]"}`}>
                <GoalRing progress={goalProgress} isDark={isDark} />
              </div>
            </div>
          </SettingsCard>

          <section className={`rounded-[1.35rem] border-2 p-5 ${isDark ? "border-slate-700/70 bg-[#111820]" : "border-slate-200 bg-white"}`}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border ${isDark ? "border-rose-400/20 bg-rose-400/8 text-rose-300" : "border-rose-200 bg-rose-50 text-rose-600"}`}>
                  <SignOutIcon />
                </div>
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Sign out</p>
                  <h2 className={`mt-2 text-[1.45rem] font-semibold tracking-[-0.02em] ${isDark ? "text-[#f3ede4]" : "text-stone-950"}`}>Sign out</h2>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>You&apos;ll be signed out of this workspace on this device.</p>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className={`inline-flex items-center justify-center rounded-[0.95rem] border px-5 py-2.5 text-sm font-semibold transition ${
                  isDark ? "border-rose-400/30 text-rose-300 hover:bg-rose-500/10" : "border-rose-200 text-rose-600 hover:bg-rose-50"
                }`}
              >
                Sign out
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function modeLabel(mode: string) {
  return MODES.find((item) => item.value === mode)?.label ?? "Casual"
}

function primaryActionClass(isDark: boolean, wide = false) {
  return `inline-flex items-center justify-center rounded-[0.8rem] px-4 py-2.5 text-sm font-semibold transition disabled:opacity-60 ${
    wide ? "sm:px-5" : ""
  } ${isDark ? "bg-[#165c52] text-white hover:bg-[#1a695e]" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`
}

function SettingsCard({
  isDark,
  icon,
  eyebrow,
  title,
  description,
  sideNote,
  stacked = false,
  children,
}: {
  isDark: boolean
  icon: ReactNode
  eyebrow: string
  title: string
  description: ReactNode
  sideNote?: string
  stacked?: boolean
  children: ReactNode
}) {
  return (
    <section className={`min-w-0 rounded-[1.2rem] border-2 p-5 ${isDark ? "border-slate-700/70 bg-[#11171d]" : "border-slate-200 bg-white"}`}>
      <div className={stacked ? "grid gap-5" : "grid gap-5 xl:grid-cols-[180px_minmax(0,1fr)] 2xl:grid-cols-[220px_minmax(0,1fr)]"}>
        <div className="min-w-0 flex items-start gap-4">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 ${isDark ? "border-slate-700/70 bg-[#182028] text-[#7fd2bf]" : "border-slate-200 bg-[#edf6f4] text-[#1f615d]"}`}>
            {icon}
          </div>
          <div>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{eyebrow}</p>
            <h2 className={`mt-2 text-[1.3rem] font-semibold tracking-[-0.025em] ${isDark ? "text-[#f3ede4]" : "text-stone-950"}`}>{title}</h2>
            <div className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{description}</div>
          </div>
        </div>

        <div className="min-w-0">
          {sideNote ? <p className={`mb-4 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{sideNote}</p> : null}
          {children}
        </div>
      </div>
    </section>
  )
}

function SummaryCard({ isDark, icon, label, value, note }: { isDark: boolean; icon: ReactNode; label: string; value: string; note: string }) {
  return (
    <div className={`min-w-0 overflow-hidden rounded-[1.15rem] border-2 p-5 ${isDark ? "border-slate-700/70 bg-[#11171d]" : "border-slate-200 bg-white"}`}>
      <div className="flex items-center justify-between gap-3">
        <div className={`flex h-12 w-12 items-center justify-center rounded-full border-2 ${isDark ? "border-slate-700/70 bg-[#172029] text-[#7fd2bf]" : "border-slate-200 bg-[#edf6f4] text-[#1f615d]"}`}>
          {icon}
        </div>
        <span className={`${isDark ? "text-slate-500" : "text-stone-400"}`}>
          <ChevronRightIcon />
        </span>
      </div>
      <p className={`mt-4 text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{label}</p>
      <p className={`mt-2 text-[1.55rem] font-semibold tracking-[-0.03em] ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
      <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{note}</p>
    </div>
  )
}

function InfoItem({ isDark, label, value }: { isDark: boolean; label: string; value: string }) {
  return (
    <div className={`min-w-0 overflow-hidden rounded-[1rem] border-2 p-4 ${isDark ? "border-slate-700/70 bg-[#121921]" : "border-slate-200 bg-[#fbfcfd]"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{label}</p>
      <p className={`mt-3 truncate text-base font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
    </div>
  )
}

function SelectableCard({
  isDark,
  active,
  title,
  description,
  icon,
  disabled = false,
  onClick,
}: {
  isDark: boolean
  active: boolean
  title: string
  description: string
  icon: ReactNode
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`min-w-0 rounded-[1rem] border-2 p-4 text-left transition disabled:opacity-60 ${
        active
          ? isDark
            ? "border-[#3a9d89] bg-[#14211f]"
            : "border-[#5ca79b] bg-[#f4faf8]"
          : isDark
            ? "border-slate-700/70 bg-[#121921] hover:bg-[#15202a]"
            : "border-slate-200 bg-[#fbfcfd] hover:bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className={`${active ? (isDark ? "text-[#7fd2bf]" : "text-[#1f615d]") : isDark ? "text-slate-400" : "text-stone-500"}`}>{icon}</div>
          <div>
            <p className={`text-lg font-semibold tracking-[-0.02em] ${isDark ? "text-white" : "text-stone-950"}`}>{title}</p>
            <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{description}</p>
          </div>
        </div>
        <span className={`mt-1 flex h-5 w-5 items-center justify-center rounded-full border ${active ? (isDark ? "border-[#2f8a78]" : "border-[#76b4aa]") : isDark ? "border-slate-600" : "border-stone-300"}`}>
          {active ? <span className={`h-2.5 w-2.5 rounded-full ${isDark ? "bg-[#59c3ad]" : "bg-[#1f615d]"}`} /> : null}
        </span>
      </div>
    </button>
  )
}

function InlineMessage({ isDark, message, tone, className = "" }: { isDark: boolean; message: string; tone: "warning" | "neutral"; className?: string }) {
  const classes =
    tone === "warning"
      ? isDark
        ? "border-amber-400/20 bg-amber-300/10 text-amber-100"
        : "border-amber-300/40 bg-amber-100/70 text-amber-900"
      : isDark
        ? "border-white/[0.08] bg-white/[0.03] text-slate-300"
        : "border-[#dde2e8] bg-[#f8fafb] text-stone-700"

  return <div className={`rounded-[1rem] border px-4 py-3 text-sm ${classes} ${className}`.trim()}>{message}</div>
}

function GoalRing({ progress, isDark }: { progress: number; isDark: boolean }) {
  const circumference = 2 * Math.PI * 34
  const dashOffset = circumference - (progress / 100) * circumference

  return (
    <div className="relative flex h-28 w-28 items-center justify-center">
      <svg className="h-28 w-28 -rotate-90" viewBox="0 0 84 84" aria-hidden="true">
        <circle cx="42" cy="42" r="34" fill="none" stroke={isDark ? "rgba(255,255,255,0.08)" : "rgba(148,163,184,0.22)"} strokeWidth="8" />
        <circle
          cx="42"
          cy="42"
          r="34"
          fill="none"
          stroke={isDark ? "#59c3ad" : "#1f615d"}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="absolute text-center">
        <p className={`text-[1.4rem] font-semibold tracking-[-0.03em] ${isDark ? "text-white" : "text-stone-950"}`}>{progress}%</p>
        <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>of goal</p>
      </div>
    </div>
  )
}

function PlanIcon() {
  return <BookmarkIcon />
}

function ReadingIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 6.5A2.5 2.5 0 017 4h5v15H7a2.5 2.5 0 00-2.5 2.5V6.5zM19.5 6.5A2.5 2.5 0 0017 4h-5v15h5a2.5 2.5 0 012.5 2.5V6.5z" />
    </svg>
  )
}

function ThemeIcon({ dark }: { dark: boolean }) {
  return dark ? <MoonIcon /> : <SunIcon />
}

function BillingIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="4" y="6" width="16" height="12" rx="2.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 10h16" />
    </svg>
  )
}

function IdentityIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 12a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM5 19a7 7 0 0114 0" />
    </svg>
  )
}

function AppearanceIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 19l14-14M9 5l10 10M5 15l4 4" />
    </svg>
  )
}

function AnswerStyleIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" />
    </svg>
  )
}

function PrivacyIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l7 3v5c0 4.5-2.7 7.5-7 9-4.3-1.5-7-4.5-7-9V7l7-3z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.5 12.5l1.6 1.6 3.4-3.4" />
    </svg>
  )
}

function GoalIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <circle cx="12" cy="12" r="7.5" />
      <circle cx="12" cy="12" r="3" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 12l6-6" />
    </svg>
  )
}

function SignOutIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 7H6.5A2.5 2.5 0 004 9.5v7A2.5 2.5 0 006.5 19H10" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 8l4 4-4 4M18 12h-8" />
    </svg>
  )
}

function BookmarkIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 4.5h10v15l-5-3-5 3v-15z" />
    </svg>
  )
}

function SunIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3.5v2M12 18.5v2M20.5 12h-2M5.5 12h-2M18 6l-1.4 1.4M7.4 16.6L6 18M18 18l-1.4-1.4M7.4 7.4L6 6M15.5 12a3.5 3.5 0 11-7 0 3.5 3.5 0 017 0z" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20 14.5A8.5 8.5 0 119.5 4 6.8 6.8 0 0020 14.5z" />
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 7.5h12A2.5 2.5 0 0120.5 10v4A2.5 2.5 0 0118 16.5h-6L7 20v-3.5H6A2.5 2.5 0 013.5 14v-4A2.5 2.5 0 016 7.5z" />
    </svg>
  )
}

function BarsIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18V10M12 18V6M18 18v-8" />
    </svg>
  )
}

function BoltIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 3L6 13h5l-1 8 8-11h-5l0-7z" />
    </svg>
  )
}

function GlobeIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <circle cx="12" cy="12" r="8.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.5 12h17M12 3.5c2.4 2.6 3.7 5.5 3.7 8.5S14.4 17.9 12 20.5M12 3.5C9.6 6.1 8.3 9 8.3 12s1.3 5.9 3.7 8.5" />
    </svg>
  )
}

function FriendsIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 11a3 3 0 100-6 3 3 0 000 6zM4 19a5 5 0 0110 0M17 11a2.5 2.5 0 100-5M15.5 15.5A4.5 4.5 0 0120 20" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 6l6 6-6 6" />
    </svg>
  )
}

function CheckCircleIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <circle cx="12" cy="12" r="9" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.7 12.2l2.1 2.1 4.5-4.5" />
    </svg>
  )
}
