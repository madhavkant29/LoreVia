"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import "./settings.css"

import {
  BarsIcon,
  BoltIcon,
  CheckCircleIcon,
  COMPLEXITY_OPTIONS,
  FriendsIcon,
  GlobeIcon,
  GoalRing,
  InfoItem,
  InlineMessage,
  MailIcon,
  MODES,
  modeLabel,
  MoonIcon,
  PlanIcon,
  ReadingIcon,
  SelectableCard,
  SETTINGS_NAV,
  SETTINGS_SEARCH_TERMS,
  SettingsPanel,
  SettingsSearchContext,
  ShieldIcon,
  SunIcon,
  SummaryCard,
  ThemeIcon,
  useActiveSettingsSection,
} from "./settingsPage.components"

import { authApi } from "@/lib/api/auth"
import { clearAuthCookies } from "@/lib/api/client"
import { billingApi } from "@/lib/api/billing"
import { supportApi } from "@/lib/api/support"
import { ANALYTICS_CONSENT_COOKIE, getAnalyticsConsentValue } from "@/lib/analytics/posthogConsent"
import { emailApi } from "@/lib/api/email"
import { tierLabel } from "@/lib/billing/plans"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { getTrialCountdown } from "@/lib/billing/trialCountdown"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { toolsForPlacement } from "@/lib/workspace/toolRegistry"
import type { EmailPreferences } from "@/types/email"
import type { SupportConfig } from "@/types/support"

const DELETION_REQUEST_EMAIL = "support@mail.getlorevia.com"
const DASHBOARD_VISIBILITY_TOOLS = toolsForPlacement("dashboard").filter((tool) => !tool.nonHideable)

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
  const [emailPreferences, setEmailPreferences] = useState<EmailPreferences | null>(null)
  const [supportConfig, setSupportConfig] = useState<SupportConfig | null>(null)
  const [communityMessage, setCommunityMessage] = useState<string | null>(null)
  const [workspaceMessage, setWorkspaceMessage] = useState<string | null>(null)
  const [emailPreferencesLoading, setEmailPreferencesLoading] = useState(false)
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
  const displayTier = stableUser?.tier_label ?? tierLabel(stableUser?.tier)
  const purchasedTier = tierLabel(stableUser?.plan_tier)
  const paidUser = Boolean(stableUser && stableUser.tier !== "free" && !stableUser.trial_active)
  const trialEndsLabel = stableUser?.trial_ends_at
    ? new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(stableUser.trial_ends_at))
    : null
  const trialCountdown = getTrialCountdown(stableUser?.trial_ends_at, trialCountdownNow)
  const refundRequestHref = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("LoreVia refund request")}`

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

  useEffect(() => {
    if (!stableUser?.email) return
    let cancelled = false
    setEmailPreferencesLoading(true)
    setEmailPreferencesMessage(null)
    void emailApi
      .getPreferences()
      .then((preferences) => {
        if (!cancelled) {
          setEmailPreferences(preferences)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setEmailPreferencesMessage("We could not load your email preferences right now.")
        }
      })
      .finally(() => {
        if (!cancelled) {
          setEmailPreferencesLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [stableUser?.email])

  useEffect(() => {
    if (!stableUser?.email) return
    let cancelled = false
    void supportApi.config()
      .then((config) => {
        if (cancelled) return
        setSupportConfig(config)
      })
      .catch(() => {
        if (!cancelled) setCommunityMessage("Community settings could not load right now.")
      })
    return () => {
      cancelled = true
    }
  }, [stableUser?.email])

  const changeMode = async (mode: string) => {
    await authApi.setReadingMode(mode)
    if (user) setUser({ ...user, reading_mode: mode as "casual" | "analyst" | "speed" })
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
    document.cookie = `${ANALYTICS_CONSENT_COOKIE}=${value}; Max-Age=31536000; Path=/; SameSite=Lax`
    setAnalyticsConsent(value)
    if (value === "false") {
      window.localStorage.removeItem("ph_phc_posthog")
      window.localStorage.removeItem("ph_lorevia_posthog")
    }
  }

  const exportData = async () => {
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
    if (accountDeleteConfirmation !== "DELETE MY ACCOUNT") return
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
      setAccountDeleteBusy(false)
    }
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
      const nextUsername = updated.username ?? trimmedUsername
      setUsernameDraft(nextUsername)
      setConfirmedUsername(nextUsername)
      setUsernameMessage(confirmedUsername ? "Public username updated." : "Public username saved.")
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
  const { activeSectionId, setActiveSectionId } = useActiveSettingsSection()
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

  const summaryCards = useMemo(
    () => [
      { label: "Plan", value: displayTier, icon: <PlanIcon /> },
      { label: "Reading mode", value: modeLabel(currentReadingMode), icon: <ReadingIcon /> },
      { label: "Theme", value: theme === "dark" ? "Dark" : "Light", icon: <ThemeIcon dark={isDark} /> },
    ],
    [currentReadingMode, displayTier, isDark, theme],
  )

  return (
    <div className={`settings-surface ${isDark ? "settings-surface--dark" : "settings-surface--light"}`}>
      <div className="mx-auto max-w-[1040px] pb-10">
        <header className="settings-hero">
          <div>
            <p className="settings-kicker">Settings</p>
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
          <div className="settings-summary-grid">
            {summaryCards.map((card) => (
              <SummaryCard key={card.label} icon={card.icon} label={card.label} value={card.value} />
            ))}
          </div>
        </header>

        <div className="settings-layout">
          <nav className="settings-section-nav" aria-label="Settings sections">
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
              <div className="settings-info-grid">
                {stableUser?.email ? <InfoItem label="Email" value={stableUser.email} /> : null}
                <InfoItem label="Plan status" value={displayTier} />
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
              ) : (
                <p className="settings-copy mt-5">
                  Purchased plan: {purchasedTier}. Cancel renewal, payment method changes, and invoice access live in the billing portal.
                </p>
              )}
              {paidUser ? (
                <>
                  <p className="settings-copy mt-3">Manage your payment details, invoices, and subscription access in the billing portal.</p>
                  <button onClick={openBillingPortal} disabled={billingBusy} className="settings-primary-button mt-5">
                    {billingBusy ? "Opening billing..." : "Manage billing / cancel subscription"}
                  </button>
                  <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm font-semibold text-[#1f615d]">
                    <a href="/refund" className="underline underline-offset-4">Refund policy</a>
                    <a href={refundRequestHref} className="underline underline-offset-4">Request a refund</a>
                  </div>
                </>
              ) : (
                <button onClick={() => router.push("/upgrade")} className="settings-primary-button mt-5">
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
                      minLength={3}
                      maxLength={32}
                      autoComplete="username"
                      value={usernameDraft}
                      onChange={(event) => setUsernameDraft(event.target.value)}
                      onInput={(event) => setUsernameDraft((event.target as HTMLInputElement).value)}
                      className="settings-input"
                    />
                    <span className={usernameDraft.trim().length >= 3 ? "settings-check settings-check--valid" : "settings-check"}>
                      <CheckCircleIcon />
                    </span>
                  </div>
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
                  <button onClick={saveUsername} disabled={usernameSaving || usernameDraft.trim().length < 3} className="settings-primary-button mt-5">
                    {usernameSaving ? "Saving..." : stableUser?.username ? "Change username" : "Save username"}
                  </button>
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
                        className={hidden ? "settings-secondary-button" : "settings-danger-button"}
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
                    onClick={() => changeMode(mode.value)}
                  />
                ))}
              </div>
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
                    disabled={permissionSaving}
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
              {communityMessage ? <InlineMessage message={communityMessage} tone="neutral" className="mt-4" /> : null}
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
              {emailPreferencesLoading ? <InlineMessage message="Loading email preferences..." tone="neutral" className="mt-4" /> : null}
              {emailPreferencesMessage ? <InlineMessage message={emailPreferencesMessage} tone="neutral" className="mt-4" /> : null}
              <p className="settings-security-note mt-4">
                <ShieldIcon /> Security, password reset, verification, and billing emails will always be sent even when promotional emails are turned off.
              </p>
            </SettingsPanel>

            <SettingsPanel id="goals" title="Daily writing target">
              <div className="settings-goal-grid">
                <label>
                  <span className="settings-label">Words per day</span>
                  <input
                    type="number"
                    min={1}
                    value={goalDraft}
                    onChange={(event) => setGoalDraft(event.target.value)}
                    className="settings-number-input mt-2"
                  />
                  <button onClick={saveDailyGoal} disabled={goalSaving} className="settings-primary-button mt-4">
                    {goalSaving ? "Saving..." : "Save daily goal"}
                  </button>
                </label>

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
                  <GoalRing progress={goalProgress} />
                </div>
              </div>
            </SettingsPanel>

            <SettingsPanel id="session" title="Sign out" compact>
              <div className="settings-session-row">
                <p className="settings-copy">You&apos;ll be signed out of this workspace on this device.</p>
                <button onClick={handleLogout} className="settings-danger-button">
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
                    id="account-delete-password"
                    type="password"
                    value={accountDeletePassword}
                    onChange={(event) => setAccountDeletePassword(event.target.value)}
                    className="settings-input mt-2"
                    autoComplete="current-password"
                  />
                  <button
                    onClick={deleteAccount}
                    disabled={accountDeleteBusy || accountDeleteConfirmation !== "DELETE MY ACCOUNT"}
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
