"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import "./settings.css"

import {
  BarsIcon,
  BoltIcon,
  COMPLEXITY_OPTIONS,
  FriendsIcon,
  GlobeIcon,
  InfoItem,
  InlineMessage,
  MailIcon,
  MODES,
  MoonIcon,
  ReadingIcon,
  SelectableCard,
  SETTINGS_NAV,
  SETTINGS_SEARCH_TERMS,
  SettingsPanel,
  SettingsSearchContext,
  ShieldIcon,
  SunIcon,
  useActiveSettingsSection,
} from "./settingsPage.components"

import { authApi } from "@/lib/api/auth"
import { clearAuthCookies } from "@/lib/api/client"
import { billingApi } from "@/lib/api/billing"
import { supportApi } from "@/lib/api/support"
import { getAnalyticsConsentValue, writeAnalyticsConsentCookie } from "@/lib/analytics/posthogConsent"
import { emailApi } from "@/lib/api/email"
import { getTrialCountdown } from "@/lib/billing/trialCountdown"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import type { EmailPreferences } from "@/types/email"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { useSettingsDraftGuard, useSettingsResource } from "./settingsPage.state"
import { DASHBOARD_VISIBILITY_TOOLS, DELETION_REQUEST_EMAIL, dailyGoalError, formatBillingDate, getBillingPresentation, usernameError } from "./settingsPage.helpers"

export default function SettingsPage() {
  const { user, setUser, logout } = useAuthStore()
  const authHydrated = useAuthStore((state) => state.hydrated)
  const { theme, setTheme } = usePreferencesStore()
  const uiPreferences = useUiPreferencesStore((state) => state.preferences)
  const setComplexityMode = useUiPreferencesStore((state) => state.setComplexityMode)
  const setDashboardToolVisibility = useUiPreferencesStore((state) => state.setDashboardToolVisibility)
  const restartGuidance = useUiPreferencesStore((state) => state.restartGuidance)
  const retryUiPreferenceSync = useUiPreferencesStore((state) => state.retrySync)
  const uiPreferenceSyncState = useUiPreferencesStore((state) => state.syncState)
  const uiPreferenceSyncMessage = useUiPreferencesStore((state) => state.syncMessage)
  const isDark = theme === "dark"
  const [billingBusy, setBillingBusy] = useState(false)
  const [billingMessage, setBillingMessage] = useState<string | null>(null)
  const [goalDraft, setGoalDraft] = useState("1000")
  const [goalSaving, setGoalSaving] = useState(false)
  const [goalMessage, setGoalMessage] = useState<string | null>(null)
  const [usernameDraft, setUsernameDraft] = useState("")
  const [confirmedUsername, setConfirmedUsername] = useState("")
  const [usernameSaving, setUsernameSaving] = useState(false)
  const [usernameMessage, setUsernameMessage] = useState<string | null>(null)
  const [permissionSaving, setPermissionSaving] = useState(false)
  const [permissionMessage, setPermissionMessage] = useState<string | null>(null)
  const [workspaceMessage, setWorkspaceMessage] = useState<string | null>(null)
  const [emailPreferencesSaving, setEmailPreferencesSaving] = useState(false)
  const [emailPreferencesMessage, setEmailPreferencesMessage] = useState<string | null>(null)
  const [dataExportBusy, setDataExportBusy] = useState(false)
  const [dataExportMessage, setDataExportMessage] = useState<string | null>(null)
  const [accountDeleteConfirmation, setAccountDeleteConfirmation] = useState("")
  const [accountDeletePassword, setAccountDeletePassword] = useState("")
  const [accountDeleteBusy, setAccountDeleteBusy] = useState(false)
  const [accountDeleteMessage, setAccountDeleteMessage] = useState<string | null>(null)
  const [analyticsConsent, setAnalyticsConsent] = useState<string | undefined>(undefined)
  const [trialCountdownNow, setTrialCountdownNow] = useState(() => Date.now())
  const [settingsQuery, setSettingsQuery] = useState("")
  const router = useRouter()
  const stableUser = authHydrated ? user : null
  const billing = useSettingsResource(stableUser?.email, billingApi.subscription)
  const emails = useSettingsResource(stableUser?.email, emailApi.getPreferences)
  const community = useSettingsResource(stableUser?.email, supportApi.config)
  const billingStatus = billing.data
  const emailPreferences = emails.data
  const setEmailPreferences = emails.setData
  const supportConfig = community.data
  const [modeSaving, setModeSaving] = useState(false)
  const [modeMessage, setModeMessage] = useState<string | null>(null)
  const accountLock = useRef(false)
  const accountSaving = modeSaving || goalSaving || usernameSaving || permissionSaving || accountDeleteBusy
  const goalValidation = dailyGoalError(goalDraft)
  const usernameValidation = usernameError(usernameDraft)
  const goalDirty = goalDraft !== String(stableUser?.daily_word_goal ?? 1000)
  const usernameDirty = usernameDraft.trim() !== confirmedUsername
  const allowLeave = useSettingsDraftGuard(!!stableUser && (goalDirty || usernameDirty), accountSaving || emailPreferencesSaving || accountDeleteBusy)
  const {
    paidUser,
    displayTier,
    billingDisplayState,
    billingPlanLabel,
    billingPriceLabel,
    nextRenewalLabel,
    cancellationEndLabel,
    refundRequestHref,
  } = getBillingPresentation(billingStatus, stableUser)
  const trialEndsLabel = stableUser?.trial_ends_at
    ? formatBillingDate(stableUser.trial_ends_at)
    : null
  const trialCountdown = getTrialCountdown(stableUser?.trial_ends_at, trialCountdownNow)

  useEffect(() => {
    setGoalDraft(String(stableUser?.daily_word_goal ?? 1000))
  }, [stableUser?.daily_word_goal])

  useEffect(() => {
    const nextUsername = stableUser?.username ?? ""
    setUsernameDraft(nextUsername)
    setConfirmedUsername(nextUsername)
  }, [stableUser?.username])

  useEffect(() => {
    if (!stableUser?.trial_active) return
    setTrialCountdownNow(Date.now())
    const timer = window.setInterval(() => setTrialCountdownNow(Date.now()), 60_000)
    return () => window.clearInterval(timer)
  }, [stableUser?.trial_active])

  useEffect(() => {
    setAnalyticsConsent(getAnalyticsConsentValue(document.cookie))
  }, [])

  const changeMode = async (mode: string) => {
    if (accountLock.current || mode === stableUser?.reading_mode) return
    accountLock.current = true; setModeSaving(true); setModeMessage(null)
    try {
      const updated = await authApi.setReadingMode(mode)
      setUser(updated)
      setModeMessage("Reading mode updated.")
    } catch { setModeMessage("Reading mode could not be saved. Your previous mode is unchanged. Try again.") }
    finally { accountLock.current = false; setModeSaving(false) }
  }

  const dashboardToolHidden = (toolId: string) => {
    const visibility = uiPreferences.dashboard_visibility[toolId]
    return visibility === false || visibility === "user_hidden"
  }

  const changeDashboardToolVisibility = (toolId: string, hidden: boolean) => {
    if (toolId === "dashboard.pricing" && !paidUser) return
    setWorkspaceMessage(null)
    void setDashboardToolVisibility(toolId, hidden ? "user_hidden" : "visible")
  }

  const hiddenDashboardToolCount = DASHBOARD_VISIBILITY_TOOLS.filter((tool) => dashboardToolHidden(tool.id)).length

  const showAllHiddenDashboardTools = async () => {
    setWorkspaceMessage(null)
    const hiddenTools = DASHBOARD_VISIBILITY_TOOLS.filter((tool) => dashboardToolHidden(tool.id))
    await Promise.all(hiddenTools.map((tool) => setDashboardToolVisibility(tool.id, "visible")))
    setWorkspaceMessage("All hidden workspace tools are visible again.")
  }

  const handleRestartGuidance = async () => {
    setWorkspaceMessage(null)
    await restartGuidance()
    setWorkspaceMessage("Onboarding tips and guidance will appear again where available.")
  }

  const handleLogout = async () => {
    if (!allowLeave()) return
    try {
      await authApi.logout()
    } catch {
      // A failed remote logout must not leave authenticated client state behind.
    } finally {
      logout()
      document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
      clearAuthCookies()
      router.replace("/login")
    }
  }

  const setAnalyticsCookie = (value: "true" | "false") => {
    writeAnalyticsConsentCookie(value)
    setAnalyticsConsent(value)
  }

  const exportData = async () => {
    if (dataExportBusy || accountDeleteBusy) return
    setDataExportBusy(true)
    setDataExportMessage(null)
    try {
      const blob = await authApi.exportData()
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = "lorevia-data-export.zip"
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setDataExportMessage("Your data export download has started.")
    } catch {
      setDataExportMessage(`We could not prepare your export right now. You can email ${DELETION_REQUEST_EMAIL} for help.`)
    } finally {
      setDataExportBusy(false)
    }
  }

  const deleteAccount = async () => {
    if (accountLock.current || accountDeleteBusy || emailPreferencesSaving || accountDeleteConfirmation !== "DELETE MY ACCOUNT") return
    accountLock.current = true
    setAccountDeleteBusy(true)
    setAccountDeleteMessage(null)
    try {
      await authApi.deleteAccount({
        confirmationText: accountDeleteConfirmation,
        password: accountDeletePassword,
      })
      logout()
      clearAuthCookies()
      document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
      router.replace("/login")
    } catch {
      setAccountDeleteMessage("We could not delete your account. Check your confirmation and password, or contact support.")
    } finally {
      accountLock.current = false
      setAccountDeleteBusy(false)
    }
  }

  const openBillingPortal = async () => {
    if (billingBusy || accountDeleteBusy) return
    setBillingBusy(true)
    setBillingMessage(null)
    try {
      const result = await billingApi.portal()
      if (!result.billing_enabled || !result.portal_url) {
        setBillingMessage(result.message ?? "Billing is not configured in this environment yet.")
        return
      }
      if (allowLeave()) window.location.href = result.portal_url
    } catch {
      setBillingMessage("We could not open the billing portal right now. Please try again in a moment.")
    } finally {
      setBillingBusy(false)
    }
  }

  const saveDailyGoal = async () => {
    if (accountLock.current || goalValidation) return
    const parsedGoal = Number(goalDraft)
    accountLock.current = true

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
      accountLock.current = false; setGoalSaving(false)
    }
  }

  const saveUsername = async () => {
    const trimmedUsername = usernameDraft.trim()
    if (accountLock.current || usernameValidation) return
    accountLock.current = true

    setUsernameSaving(true)
    setUsernameMessage(null)
    try {
      const updated = await authApi.setUsername(trimmedUsername)
      setUser(updated)
      const nextUsername = updated.username ?? trimmedUsername
      setUsernameDraft(nextUsername)
      setConfirmedUsername(nextUsername)
      setUsernameMessage(confirmedUsername ? "Public username updated." : "Public username saved.")
    } catch {
      setUsernameMessage("We could not save that username. Try a different handle with letters, numbers, hyphens, or underscores.")
    } finally {
      accountLock.current = false; setUsernameSaving(false)
    }
  }

  const changeMessagingPermission = async (messagingPermission: "anyone" | "friends_only") => {
    if (accountLock.current || messagingPermission === stableUser?.messaging_permission) return
    accountLock.current = true
    setPermissionSaving(true)
    setPermissionMessage(null)
    try {
      const updated = await authApi.setMessagingPermission(messagingPermission)
      setUser(updated)
      setPermissionMessage("Messaging privacy updated.")
    } catch {
      setPermissionMessage("We could not save your messaging privacy right now.")
    } finally {
      accountLock.current = false; setPermissionSaving(false)
    }
  }

  const saveEmailPreferences = async (next: EmailPreferences) => {
    setEmailPreferencesSaving(true)
    setEmailPreferencesMessage(null)
    try {
      const updated = await emailApi.updatePreferences({
        product_updates: next.product_updates,
        marketing: next.marketing,
      })
      setEmailPreferences(updated)
      setEmailPreferencesMessage("Email preferences updated.")
    } catch {
      setEmailPreferencesMessage("We could not save your email preferences right now.")
    } finally {
      setEmailPreferencesSaving(false)
    }
  }

  const changeEmailPreference = (key: "product_updates" | "marketing") => {
    if (!emailPreferences || emailPreferencesSaving) return
    const next = {
      ...emailPreferences,
      [key]: !emailPreferences[key],
    }
    next.unsubscribed_all = !next.product_updates && !next.marketing
    void saveEmailPreferences(next)
  }

  const unsubscribeFromPromotionalEmails = () => {
    if (!emailPreferences || emailPreferencesSaving || emailPreferences.unsubscribed_all) return
    void saveEmailPreferences({
      ...emailPreferences,
      product_updates: false,
      marketing: false,
      unsubscribed_all: true,
    })
  }

  const dailyGoal = stableUser?.daily_word_goal ?? 1000
  const todayWords = stableUser?.today_word_count ?? 0
  const goalProgress = Math.max(0, Math.min(100, Math.round((todayWords / Math.max(dailyGoal, 1)) * 100)))
  const currentReadingMode = stableUser?.reading_mode ?? "casual"
  const currentPermission = stableUser?.messaging_permission ?? "anyone"
  const { activeSectionId, setActiveSectionId } = useActiveSettingsSection(settingsQuery, authHydrated)
  const matchingSectionIds = useMemo(() => {
    const query = settingsQuery.trim().toLowerCase()
    if (!query) return new Set(SETTINGS_NAV.map((item) => item.id))
    const terms = query.split(/\s+/).filter(Boolean)
    return new Set(
      SETTINGS_NAV
        .filter((item) => {
          const haystack = `${item.label} ${SETTINGS_SEARCH_TERMS[item.id] ?? ""}`.toLowerCase()
          return terms.every((term) => haystack.includes(term))
        })
        .map((item) => item.id),
    )
  }, [settingsQuery])

  if (!authHydrated) return <p role="status" className="py-6 text-sm">Loading account settings…</p>
  if (!stableUser) return <p className="py-6 text-sm">Sign in to manage your settings.</p>

  return (
    <div data-settings-workspace className={`settings-surface ${isDark ? "settings-surface--dark" : "settings-surface--light"}`}>
      <div className="mx-auto max-w-[1040px] pb-10">
        <header className="settings-hero">
          <div>
            <h1 className="settings-title">Settings</h1>
            <p className="settings-intro">Manage your account, workspace preferences, privacy, and writing goals.</p>
            <label className="mt-5 block max-w-lg">
              <span className="sr-only">Search settings</span>
              <input
                type="search"
                value={settingsQuery}
                onChange={(event) => setSettingsQuery(event.target.value)}
                placeholder="Search account, visibility, privacy, security..."
                className="settings-input"
              />
            </label>
          </div>
          <button type="button" className="settings-secondary-button" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>
        </header>
        {settingsQuery ? <div className="mb-5 flex flex-wrap items-center gap-4 text-sm"><p role="status">{matchingSectionIds.size} matching settings sections</p><button type="button" className="settings-secondary-button" onClick={() => setSettingsQuery("")}>Clear search</button></div> : null}
        {usernameDirty || goalDirty ? <p role="status" className="settings-copy mb-5">Unsaved changes: {[usernameDirty ? "public username" : "", goalDirty ? "daily goal" : ""].filter(Boolean).join(" and ")}. Save each field below.</p> : null}

        <div className="settings-layout">
          <nav className="settings-section-nav" aria-label="Settings sections">
            <label className="block text-sm font-medium lg:hidden">Jump to section<select aria-label="Jump to settings section" className="settings-input mt-2" value={matchingSectionIds.has(activeSectionId) ? activeSectionId : ""} onChange={(event) => { setActiveSectionId(event.target.value); document.getElementById(event.target.value)?.scrollIntoView({ behavior: "smooth", block: "start" }) }}><option value="" disabled>Choose a section</option>{SETTINGS_NAV.filter((item) => matchingSectionIds.has(item.id)).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
            <div className="hidden lg:block">
            {SETTINGS_NAV.filter((item) => matchingSectionIds.has(item.id)).map((item) => {
              const active = activeSectionId === item.id
              return (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  aria-current={active ? "location" : undefined}
                  className={active ? "settings-section-nav__item settings-section-nav__item--active" : "settings-section-nav__item"}
                  onClick={() => setActiveSectionId(item.id)}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </a>
              )
            })}
            </div>
          </nav>

          <SettingsSearchContext.Provider value={matchingSectionIds}>
          <div className="settings-stack">
            {matchingSectionIds.size === 0 ? (
              <div className="settings-panel" role="status">
                <h2 className="settings-panel__title">No matching settings</h2>
                <p className="settings-copy mt-3">Try account, workspace, reading, notifications, privacy, or security.</p>
              </div>
            ) : null}
            <SettingsPanel id="account" title="Billing and account details">
              {billing.loading ? <InlineMessage message="Loading billing details…" tone="neutral" /> : null}
              {billing.failed ? <div className="mb-4"><InlineMessage message="Billing details could not be loaded. Your account plan is shown below; renewal and payment status are unverified." tone="warning" /><button type="button" className="settings-secondary-button mt-3" onClick={billing.retry}>Retry billing details</button></div> : null}
              <div className="settings-info-grid">
                {stableUser?.email ? <InfoItem label="Email" value={stableUser.email} /> : null}
                <InfoItem label="Plan status" value={displayTier} />
                {billingDisplayState === "active" && nextRenewalLabel ? (
                  <InfoItem label="Next renewal" value={nextRenewalLabel} />
                ) : null}
                {billingDisplayState === "cancellation_scheduled" && cancellationEndLabel ? (
                  <InfoItem label="Access until" value={cancellationEndLabel} />
                ) : null}
                {stableUser?.trial_active && trialCountdown ? (
                  <InfoItem label="Free trial countdown" value={trialCountdown.label} />
                ) : null}
              </div>
              {stableUser?.trial_active ? (
                <div className="mt-5 rounded-md border border-[#2b7a73]/30 bg-[#2b7a73]/5 p-4">
                  <p className="settings-copy font-semibold">Your free trial is already active.</p>
                  <p className="settings-copy mt-2">
                    You have Author trial access{trialCountdown ? ` with ${trialCountdown.label}` : ""}. It ends{trialEndsLabel ? ` on ${trialEndsLabel}` : ""}, then your account returns to Free.
                  </p>
                  <p className="settings-copy mt-2">No payment is required, and no charge is scheduled when the trial ends.</p>
                </div>
              ) : null}
              {billingDisplayState === "cancellation_scheduled" ? (
                <div className="mt-5 rounded-md border border-[#b7791f]/30 bg-[#b7791f]/5 p-4" role="status">
                  <p className="settings-copy font-semibold">Cancellation scheduled</p>
                  <p className="settings-copy mt-2">
                    Your {billingPlanLabel} plan remains active until {cancellationEndLabel ?? "the end of the current billing period"}. You won&apos;t be charged again.
                  </p>
                  <p className="settings-copy mt-2">
                    Paid access ends when the current billing period finishes, then the account moves to the Free plan.
                  </p>
                </div>
              ) : null}
              {billingDisplayState === "past_due" ? (
                <div className="mt-5 rounded-md border border-[#c53030]/30 bg-[#c53030]/5 p-4" role="alert">
                  <p className="settings-copy font-semibold">Payment issue</p>
                  <p className="settings-copy mt-2">
                    We couldn&apos;t process your latest subscription payment. Your paid access is still available while Paddle retries.
                  </p>
                  <p className="settings-copy mt-2">
                    Update your payment method in the billing portal to keep your plan active.
                  </p>
                </div>
              ) : null}
              {billingDisplayState === "active" && billingStatus ? (
                <p className="settings-copy mt-5">
                  {billingPlanLabel} — {billingPriceLabel}
                  {nextRenewalLabel ? `. Your subscription renews automatically. Next renewal on ${nextRenewalLabel}.` : ". Your subscription renews automatically until canceled."}
                </p>
              ) : null}
              {paidUser ? (
                <>
                  <p className="settings-copy mt-3">Manage your payment details, invoices, and subscription access in the billing portal.</p>
                  <button onClick={openBillingPortal} disabled={billingBusy} className="settings-primary-button mt-5">
                    {billingBusy ? "Opening billing..." : "Manage subscription"}
                  </button>
                  <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm font-semibold text-[var(--settings-accent)]">
                    <a href="/refund" className="underline underline-offset-4">Refund policy</a>
                    <a href={refundRequestHref} className="underline underline-offset-4">Request a refund</a>
                  </div>
                </>
              ) : billingStatus?.has_paddle_subscription ? (
                <>
                  <p className="settings-copy mt-3">
                    This account no longer has an active paid subscription. Invoices and past billing details remain in the portal.
                  </p>
                  <button onClick={openBillingPortal} disabled={billingBusy} className="settings-primary-button mt-5">
                    {billingBusy ? "Opening billing..." : "View billing history"}
                  </button>
                  <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm font-semibold text-[var(--settings-accent)]">
                    <a href="/refund" className="underline underline-offset-4">Refund policy</a>
                    <a href={refundRequestHref} className="underline underline-offset-4">Request a refund</a>
                  </div>
                </>
              ) : (
                <button onClick={() => { if (allowLeave()) router.push("/upgrade") }} className="settings-primary-button mt-5">
                  View paid plans
                </button>
              )}
              {billingMessage ? <InlineMessage message={billingMessage} tone="warning" className="mt-4" /> : null}
            </SettingsPanel>

            <SettingsPanel id="identity" title="Public identity">
              <div className="settings-identity-grid">
                <div>
                  <label className="settings-label" htmlFor="public-username">
                    Public username
                  </label>
                  <div className="settings-input-shell mt-2">
                    <input
                      id="public-username"
                      type="text"
                      disabled={usernameSaving}
                      aria-invalid={!!usernameValidation}
                      aria-describedby="username-rules"
                      minLength={3}
                      maxLength={32}
                      autoComplete="username"
                      value={usernameDraft}
                      onChange={(event) => setUsernameDraft(event.target.value)}
                      onInput={(event) => setUsernameDraft((event.target as HTMLInputElement).value)}
                      className="settings-input"
                    />

                  </div>
                  <p id="username-rules" className="settings-copy mt-3">Use 3–32 letters, numbers, hyphens, or underscores. Availability is checked when you save.</p>
                  <p className="settings-copy mt-3">
                    This is your public username people see on LoreVia. Your manuscript author or pen name can be changed per book.
                  </p>
                  {usernameMessage ? <InlineMessage message={usernameMessage} tone="neutral" className="mt-3" /> : null}
                </div>

                <div>
                  <p className="settings-label">Current public handle</p>
                  {confirmedUsername ? <p className="settings-handle">@{confirmedUsername}</p> : null}
                  <p className="settings-copy mt-3">
                    New author uploads default to this username, but you can change the manuscript author or pen name for any individual book.
                  </p>
                  <button onClick={saveUsername} disabled={accountSaving || !!usernameValidation || !usernameDirty} className="settings-primary-button mt-5">
                    {usernameSaving ? "Saving..." : stableUser?.username ? "Change username" : "Save username"}
                  </button>
                  {usernameDirty ? <button type="button" disabled={accountSaving} className="settings-secondary-button mt-3" onClick={() => { setUsernameDraft(confirmedUsername); setUsernameMessage(null) }}>Discard username change</button> : null}
                </div>
              </div>
            </SettingsPanel>

            <SettingsPanel id="appearance" title="Workspace theme">
              <div className="settings-choice-grid settings-choice-grid--two">
                {[
                  { value: "light", label: "Light", desc: "Clean and bright for daytime writing sessions.", icon: <SunIcon /> },
                  { value: "dark", label: "Dark", desc: "Low-glare and easier on the eyes for long writing sessions.", icon: <MoonIcon /> },
                ].map((option) => (
                  <SelectableCard
                    key={option.value}
                    active={theme === option.value}
                    title={option.label}
                    description={option.desc}
                    icon={option.icon}
                    onClick={() => setTheme(option.value as "light" | "dark")}
                  />
                ))}
              </div>
            </SettingsPanel>

            <SettingsPanel id="workspace" title="Workspace visibility">
              <div className="settings-choice-grid settings-choice-grid--three">
                {COMPLEXITY_OPTIONS.map((option) => (
                  <SelectableCard
                    key={option.value}
                    active={uiPreferences.complexity_mode === option.value}
                    title={option.label}
                    description={option.desc}
                    icon={option.icon}
                    onClick={() => void setComplexityMode(option.value)}
                  />
                ))}
              </div>
              {uiPreferenceSyncMessage ? (
                <div className="settings-session-row mt-4">
                  <InlineMessage message={uiPreferenceSyncMessage} tone="neutral" />
                  {uiPreferenceSyncState === "sync_pending" ? (
                    <button type="button" onClick={() => void retryUiPreferenceSync()} className="settings-secondary-button">
                      Retry
                    </button>
                  ) : null}
                </div>
              ) : null}
              {workspaceMessage ? (
                <div className="mt-4">
                  <InlineMessage message={workspaceMessage} tone="neutral" />
                </div>
              ) : null}
              <div className="settings-session-row mt-4">
                <div>
                  <p className="settings-tool-title">Reset workspace help</p>
                  <p className="settings-tool-state">Restart onboarding tips or restore tools you previously hid.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => void handleRestartGuidance()} className="settings-secondary-button">
                    Restart onboarding
                  </button>
                  <button
                    type="button"
                    onClick={() => void showAllHiddenDashboardTools()}
                    disabled={hiddenDashboardToolCount === 0}
                    className="settings-secondary-button"
                  >
                    Show all hidden tools
                  </button>
                </div>
              </div>
              <div className="settings-tool-list mt-5">
                {DASHBOARD_VISIBILITY_TOOLS.map((tool) => {
                  const hidden = dashboardToolHidden(tool.id)
                  const lockedVisible = tool.id === "dashboard.pricing" && !paidUser
                  return (
                    <div key={tool.id} className="settings-tool-row">
                      <div>
                        <p className="settings-tool-title">{tool.label}</p>
                        <p className="settings-tool-state">{hidden ? "Hidden from workspace navigation" : "Visible in workspace navigation"}</p>
                      </div>
                      <button
                        type="button"
                        disabled={lockedVisible}
                        onClick={() => changeDashboardToolVisibility(tool.id, !hidden)}
                        className="settings-secondary-button"
                      >
                        {lockedVisible ? "Required" : hidden ? "Show" : "Hide from workspace"}
                      </button>
                    </div>
                  )
                })}
              </div>
            </SettingsPanel>

            <SettingsPanel id="reading" title="Default reading mode">
              <div className="settings-choice-grid settings-choice-grid--three">
                {MODES.map((mode) => (
                  <SelectableCard
                    key={mode.value}
                    active={currentReadingMode === mode.value}
                    title={mode.label}
                    description={mode.desc}
                    icon={mode.value === "casual" ? <ReadingIcon /> : mode.value === "analyst" ? <BarsIcon /> : <BoltIcon />}
                    disabled={accountSaving}
                    onClick={() => void changeMode(mode.value)}
                  />
                ))}
              </div>
              {modeSaving ? <InlineMessage message="Saving reading mode…" tone="neutral" className="mt-4" /> : null}
              {modeMessage ? <InlineMessage message={modeMessage} tone="neutral" className="mt-4" /> : null}
            </SettingsPanel>

            <SettingsPanel id="privacy" title="Direct messages">
              <div className="settings-choice-grid settings-choice-grid--two">
                {[
                  { value: "anyone" as const, label: "Anyone can message me", desc: "People can open a chat immediately from search, forum, or profile entrypoints.", icon: <GlobeIcon /> },
                  { value: "friends_only" as const, label: "Friends only", desc: "People must send a friend request first, and you accept it from notifications.", icon: <FriendsIcon /> },
                ].map((option) => (
                  <SelectableCard
                    key={option.value}
                    active={currentPermission === option.value}
                    title={option.label}
                    description={option.desc}
                    icon={option.icon}
                    disabled={accountSaving}
                    onClick={() => void changeMessagingPermission(option.value)}
                  />
                ))}
              </div>
              {permissionMessage ? <InlineMessage message={permissionMessage} tone="neutral" className="mt-4" /> : null}
              <div className="settings-subsection mt-5">
                <div>
                  <p className="settings-label">Analytics consent</p>
                  <p className="settings-copy mt-2">
                    Object to or withdraw optional product analytics tracking at any time. This does not affect security, billing, or abuse-prevention logs.
                  </p>
                </div>
                <div className="settings-session-row mt-4">
                  <p className="settings-copy">
                    Current choice: {analyticsConsent === "true" ? "Allowed" : analyticsConsent === "false" ? "Withdrawn" : "Not set"}.
                  </p>
                  <div className="settings-button-row">
                    <button onClick={() => setAnalyticsCookie("true")} className="settings-secondary-button">
                      Allow analytics
                    </button>
                    <button onClick={() => setAnalyticsCookie("false")} className="settings-danger-button">
                      Withdraw analytics
                    </button>
                  </div>
                </div>
              </div>
            </SettingsPanel>

            <SettingsPanel id="community" title="Community">
              <div className="settings-session-row">
                <div>
                  <p className="settings-label">LoreVia Discord</p>
                  <p className="settings-copy mt-2">Join the general user community. Do not post private manuscript text or account details there.</p>
                </div>
                {supportConfig?.community_url ? (
                  <a href={supportConfig.community_url} target="_blank" rel="noreferrer" className="settings-primary-button">
                    Join Discord
                  </a>
                ) : (
                  <span className="settings-copy">Community link unavailable</span>
                )}
              </div>
              {community.loading ? <InlineMessage message="Loading community link…" tone="neutral" className="mt-4" /> : null}
              {community.failed ? <div className="mt-4"><InlineMessage message="Community settings could not load right now." tone="warning" /><button type="button" onClick={community.retry} className="settings-secondary-button mt-3">Retry community link</button></div> : null}
            </SettingsPanel>

            <SettingsPanel id="emails" title="LoreVia emails">
              {emailPreferences ? (
                <div>
                  <div className="settings-choice-grid settings-choice-grid--two">
                    {[
                      {
                        value: "product_updates" as const,
                        label: "Product updates",
                        desc: "Feature launches, onboarding guidance, and product news.",
                        icon: <MailIcon />,
                      },
                      {
                        value: "marketing" as const,
                        label: "Marketing emails",
                        desc: "Offers, discounts, and future promotional campaigns.",
                        icon: <ShieldIcon />,
                      },
                    ].map((option) => (
                      <SelectableCard
                        key={option.value}
                        active={emailPreferences[option.value]}
                        title={option.label}
                        description={option.desc}
                        icon={option.icon}
                        disabled={emailPreferencesSaving}
                        onClick={() => changeEmailPreference(option.value)}
                      />
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={unsubscribeFromPromotionalEmails}
                    disabled={emailPreferencesSaving || emailPreferences.unsubscribed_all}
                    className="settings-secondary-button mt-4"
                  >
                    {emailPreferences.unsubscribed_all ? "Promotional emails unsubscribed" : "Unsubscribe from promotional emails"}
                  </button>
                </div>
              ) : null}
              {emails.loading ? <InlineMessage message="Loading email preferences..." tone="neutral" className="mt-4" /> : null}
              {emails.failed ? <div className="mt-4"><InlineMessage message="Email preferences could not be loaded. Your subscription choices have not changed." tone="warning" /><button type="button" className="settings-secondary-button mt-3" onClick={emails.retry}>Retry email preferences</button></div> : null}
              {emailPreferencesMessage ? <InlineMessage message={emailPreferencesMessage} tone="neutral" className="mt-4" /> : null}
              <p className="settings-security-note mt-4">
                <ShieldIcon /> Security, password reset, verification, and billing emails will always be sent even when promotional emails are turned off.
              </p>
            </SettingsPanel>

            <SettingsPanel id="goals" title="Daily writing target">
              <div className="settings-goal-grid">
                <div>
                  <label htmlFor="daily-word-goal" className="settings-label">Words per day</label>
                  <input
                    id="daily-word-goal"
                    inputMode="numeric"
                    aria-invalid={!!goalValidation}
                    aria-describedby="daily-goal-validation"
                    disabled={goalSaving}
                    value={goalDraft}
                    onChange={(event) => setGoalDraft(event.target.value)}
                    className="settings-number-input mt-2"
                  />
                  <p id="daily-goal-validation" className="settings-copy mt-2">{goalValidation || "1 to 1,000,000 words per day."}</p>
                  <button onClick={saveDailyGoal} disabled={accountSaving || !!goalValidation || !goalDirty} className="settings-primary-button mt-4">
                    {goalSaving ? "Saving..." : "Save daily goal"}
                  </button>
                  {goalDirty ? <button type="button" disabled={accountSaving} className="settings-secondary-button mt-3" onClick={() => { setGoalDraft(String(dailyGoal)); setGoalMessage(null) }}>Discard goal change</button> : null}
                </div>

                <div className="settings-goal-today">
                  <p className="settings-label">Today</p>
                  <p className="settings-goal-count">
                    {todayWords.toLocaleString()} / {dailyGoal.toLocaleString()} words
                  </p>
                  <p className="settings-copy mt-3">Progress updates when you save manuscript edits, and your streak is based on daily sign-ins.</p>
                  {goalMessage ? <InlineMessage message={goalMessage} tone="neutral" className="mt-4" /> : null}
                </div>

                <div className="settings-progress-cell">
                  <p className="settings-label">Progress</p>
                  <p className="settings-goal-count">{goalProgress}%</p>
                  <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={goalProgress} className="settings-progress-track" aria-label={`${goalProgress}% of daily writing goal`}>
                    <span style={{ width: `${goalProgress}%` }} />
                  </div>
                </div>
              </div>
            </SettingsPanel>

            <SettingsPanel id="session" title="Sign out" compact>
              <div className="settings-session-row">
                <p className="settings-copy">You&apos;ll be signed out of this workspace on this device.</p>
                <button disabled={accountSaving || emailPreferencesSaving || accountDeleteBusy} onClick={handleLogout} className="settings-danger-button">
                  Sign out
                </button>
              </div>
            </SettingsPanel>

            <SettingsPanel id="danger" title="Danger Zone">
              <div className="settings-danger-stack">
                <div>
                  <p className="settings-label">Export my data</p>
                  <p className="settings-copy mt-2">
                    Download a machine-readable export of your account, preferences, books, manuscript text, notes, generated analysis, and beta/collaboration data.
                  </p>
                  <button onClick={exportData} disabled={dataExportBusy} className="settings-secondary-button mt-4">
                    {dataExportBusy ? "Preparing export..." : "Export my data"}
                  </button>
                  {dataExportMessage ? <InlineMessage message={dataExportMessage} tone="neutral" className="mt-3" /> : null}
                </div>

                <div className="settings-danger-box">
                  <p className="settings-label">Delete account</p>
                  <p className="settings-copy mt-2">
                    Permanently delete your LoreVia account, manuscripts, generated analysis, character data, relationships, timeline data, and public/shared links. Some billing, tax, fraud-prevention, and security records may be retained where legally required.
                  </p>
                  <p className="settings-copy mt-2">
                    To request deletion of your account or manuscript data, email {DELETION_REQUEST_EMAIL}.
                  </p>
                  <label className="settings-label mt-5 block" htmlFor="account-delete-confirmation">
                    Type DELETE MY ACCOUNT
                  </label>
                  <input
                    disabled={accountDeleteBusy}
                    id="account-delete-confirmation"
                    value={accountDeleteConfirmation}
                    onChange={(event) => setAccountDeleteConfirmation(event.target.value)}
                    className="settings-input mt-2"
                    autoComplete="off"
                  />
                  <label className="settings-label mt-4 block" htmlFor="account-delete-password">
                    Current password
                  </label>
                  <input
                    disabled={accountDeleteBusy}
                    id="account-delete-password"
                    type="password"
                    value={accountDeletePassword}
                    onChange={(event) => setAccountDeletePassword(event.target.value)}
                    className="settings-input mt-2"
                    autoComplete="current-password"
                  />
                  <button
                    onClick={deleteAccount}
                    disabled={accountSaving || emailPreferencesSaving || accountDeleteBusy || accountDeleteConfirmation !== "DELETE MY ACCOUNT"}
                    className="settings-danger-button mt-5"
                  >
                    {accountDeleteBusy ? "Deleting account..." : "Delete account"}
                  </button>
                  {accountDeleteMessage ? <InlineMessage message={accountDeleteMessage} tone="warning" className="mt-3" /> : null}
                </div>
              </div>
            </SettingsPanel>
          </div>
          </SettingsSearchContext.Provider>
        </div>
      </div>

    </div>
  )
}
