"use client"

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"

import { authApi } from "@/lib/api/auth"
import { clearAuthCookies } from "@/lib/api/client"
import { billingApi } from "@/lib/api/billing"
import { emailApi } from "@/lib/api/email"
import { tierLabel } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { EmailPreferences } from "@/types/email"

const MODES = [
  { value: "casual", label: "Casual", desc: "Quick summaries and light guidance." },
  { value: "analyst", label: "Analyst", desc: "Deeper context and richer breakdowns." },
  { value: "speed", label: "Speed", desc: "Minimal output for fast sessions." },
]

const SETTINGS_NAV = [
  { id: "account", label: "Account", icon: <IdentityIcon /> },
  { id: "identity", label: "Public identity", icon: <IdentityIcon /> },
  { id: "appearance", label: "Appearance", icon: <AppearanceIcon /> },
  { id: "reading", label: "Reading behavior", icon: <ReadingIcon /> },
  { id: "privacy", label: "Privacy", icon: <PrivacyIcon /> },
  { id: "emails", label: "Emails", icon: <MailIcon /> },
  { id: "goals", label: "Writing goals", icon: <GoalIcon /> },
  { id: "session", label: "Session", icon: <SignOutIcon /> },
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
  const [emailPreferences, setEmailPreferences] = useState<EmailPreferences | null>(null)
  const [emailPreferencesLoading, setEmailPreferencesLoading] = useState(false)
  const [emailPreferencesSaving, setEmailPreferencesSaving] = useState(false)
  const [emailPreferencesMessage, setEmailPreferencesMessage] = useState<string | null>(null)
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

  const changeMode = async (mode: string) => {
    await authApi.setReadingMode(mode)
    if (user) setUser({ ...user, reading_mode: mode as "casual" | "analyst" | "speed" })
  }

  const handleLogout = async () => {
    // Clear client state IMMEDIATELY before API call to prevent race conditions
    logout()
    document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
    clearAuthCookies()
    
    // Then make the API call in background (don't await)
    authApi.logout().catch(() => {
      // ignore logout errors - client state already cleared
    })
    
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

  const dailyGoal = stableUser?.daily_word_goal ?? 1000
  const todayWords = stableUser?.today_word_count ?? 0
  const goalProgress = Math.max(0, Math.min(100, Math.round((todayWords / Math.max(dailyGoal, 1)) * 100)))
  const currentReadingMode = stableUser?.reading_mode ?? "casual"
  const currentPermission = stableUser?.messaging_permission ?? "anyone"
  const [activeSectionId, setActiveSectionId] = useState(SETTINGS_NAV[0].id)

  const summaryCards = useMemo(
    () => [
      { label: "Plan", value: displayTier, icon: <PlanIcon /> },
      { label: "Reading mode", value: modeLabel(currentReadingMode), icon: <ReadingIcon /> },
      { label: "Theme", value: theme === "dark" ? "Dark" : "Light", icon: <ThemeIcon dark={isDark} /> },
    ],
    [currentReadingMode, displayTier, isDark, theme],
  )

  useEffect(() => {
    let frameId: number | null = null

    const updateActiveSection = () => {
      const anchorY = Math.min(window.innerHeight * 0.34, 260)
      const sections = SETTINGS_NAV
        .map((item) => {
          const element = document.getElementById(item.id)
          return element ? { id: item.id, rect: element.getBoundingClientRect() } : null
        })
        .filter((item): item is { id: string; rect: DOMRect } => Boolean(item))

      if (!sections.length) return

      const documentHeight = document.documentElement.scrollHeight
      const nearDocumentEnd =
        documentHeight > window.innerHeight &&
        window.innerHeight + window.scrollY >= documentHeight - 80
      if (nearDocumentEnd) {
        setActiveSectionId(sections.at(-1)?.id ?? SETTINGS_NAV[0].id)
        return
      }

      const visibleSections = sections.filter((section) => section.rect.bottom > 0 && section.rect.top < window.innerHeight)
      const candidates = visibleSections.length ? visibleSections : sections
      const activeSection = candidates.sort(
        (first, second) => Math.abs(first.rect.top - anchorY) - Math.abs(second.rect.top - anchorY),
      )[0]

      setActiveSectionId(activeSection.id)
    }

    const scheduleUpdate = () => {
      if (frameId !== null) return
      frameId = window.requestAnimationFrame(() => {
        frameId = null
        updateActiveSection()
      })
    }

    updateActiveSection()
    window.addEventListener("scroll", scheduleUpdate, { passive: true })
    window.addEventListener("resize", scheduleUpdate)

    return () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId)
      }
      window.removeEventListener("scroll", scheduleUpdate)
      window.removeEventListener("resize", scheduleUpdate)
    }
  }, [])

  return (
    <div className={`settings-surface ${isDark ? "settings-surface--dark" : "settings-surface--light"}`}>
      <div className="mx-auto max-w-[1040px] pb-10">
        <header className="settings-hero">
          <div>
            <p className="settings-kicker">Settings</p>
            <h1 className="settings-title">Settings</h1>
            <p className="settings-intro">Manage your account, workspace preferences, privacy, and writing goals.</p>
          </div>
          <div className="settings-summary-grid">
            {summaryCards.map((card) => (
              <SummaryCard key={card.label} icon={card.icon} label={card.label} value={card.value} />
            ))}
          </div>
        </header>

        <div className="settings-layout">
          <nav className="settings-section-nav" aria-label="Settings sections">
            {SETTINGS_NAV.map((item) => {
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

          <div className="settings-stack">
            <SettingsPanel id="account" title="Billing and account details">
              <div className="settings-info-grid">
                {stableUser?.email ? <InfoItem label="Email" value={stableUser.email} /> : null}
                <InfoItem label="Plan status" value={displayTier} />
              </div>
              {stableUser?.trial_active ? (
                <p className="settings-copy mt-5">
                  You are currently seeing Author free trial access. Your purchased plan is {purchasedTier}, so access will revert when the trial ends{trialEndsLabel ? ` on ${trialEndsLabel}` : ""} unless you upgrade.
                </p>
              ) : (
                <p className="settings-copy mt-5">
                  Purchased plan: {purchasedTier}. cancel renewal, payment method changes, and invoice access live in the billing portal.
                </p>
              )}
              <p className="settings-copy mt-3">Manage your payment details, invoices, and subscription access in the billing portal.</p>
              <button onClick={openBillingPortal} disabled={billingBusy} className="settings-primary-button mt-5">
                {billingBusy ? "Opening billing..." : "Manage billing / cancel subscription"}
              </button>
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
                  {stableUser?.username ? <p className="settings-handle">@{stableUser.username}</p> : null}
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
            </SettingsPanel>

            <SettingsPanel id="emails" title="LoreVia emails">
              {emailPreferences ? (
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
          </div>
        </div>
      </div>

      <SettingsStyles css={`
        .settings-surface {
          margin: -2rem -1rem -2rem;
          min-height: calc(100vh - 4.25rem);
          padding: 2.5rem 1rem 4rem;
          background:
            radial-gradient(circle at 85% 0%, rgba(18, 112, 103, 0.16), transparent 30rem),
            linear-gradient(180deg, #0a131a 0%, #071017 100%);
          color: #eef6f4;
        }

        .settings-surface--light {
          background:
            radial-gradient(circle at 86% 0%, rgba(28, 111, 101, 0.08), transparent 30rem),
            linear-gradient(180deg, #f6f8f9 0%, #edf2f3 100%);
          color: #0f1720;
        }

        .settings-hero {
          display: grid;
          grid-template-columns: minmax(0, 1fr);
          gap: 1.25rem;
          margin-bottom: 1.75rem;
        }

        .settings-kicker,
        .settings-label {
          color: #63e0cb;
          font-size: 0.68rem;
          font-weight: 700;
          letter-spacing: 0.24em;
          text-transform: uppercase;
        }

        .settings-surface--light .settings-kicker,
        .settings-surface--light .settings-label {
          color: #17695f;
        }

        .settings-title {
          margin-top: 0.85rem;
          font-family: var(--font-newsreader), "Iowan Old Style", Georgia, serif;
          font-size: clamp(2.45rem, 5vw, 3.35rem);
          font-weight: 500;
          line-height: 1;
          color: #fbf4ea;
        }

        .settings-surface--light .settings-title {
          color: #111827;
        }

        .settings-intro,
        .settings-copy {
          color: #b9c6d2;
          font-size: 0.92rem;
          line-height: 1.78;
        }

        .settings-intro {
          margin-top: 0.8rem;
          max-width: 32rem;
          font-size: 1rem;
        }

        .settings-surface--light .settings-intro,
        .settings-surface--light .settings-copy {
          color: #52616f;
        }

        .settings-summary-grid {
          display: grid;
          grid-template-columns: repeat(1, minmax(0, 1fr));
          gap: 0.75rem;
        }

        .settings-layout {
          display: grid;
          gap: 1.25rem;
        }

        .settings-section-nav {
          overflow: hidden;
          border: 1px solid rgba(135, 164, 184, 0.32);
          border-radius: 8px;
          background: rgba(13, 24, 32, 0.62);
          backdrop-filter: blur(18px);
        }

        .settings-surface--light .settings-section-nav {
          background: rgba(255, 255, 255, 0.82);
          border-color: rgba(148, 163, 184, 0.42);
        }

        .settings-section-nav__item {
          display: flex;
          min-height: 3.75rem;
          align-items: center;
          gap: 0.8rem;
          border-bottom: 1px solid rgba(135, 164, 184, 0.22);
          padding: 0 1rem;
          color: #b9c6d2;
          font-size: 0.9rem;
          font-weight: 500;
          transition: background-color 0.16s ease, color 0.16s ease;
        }

        .settings-section-nav__item:last-child {
          border-bottom: 0;
        }

        .settings-section-nav__item:hover,
        .settings-section-nav__item--active {
          background: rgba(84, 231, 206, 0.08);
          color: #fff;
        }

        .settings-section-nav__item--active {
          box-shadow: inset 2px 0 0 #48d9c2;
        }

        .settings-surface--light .settings-section-nav__item {
          color: #4b5c67;
        }

        .settings-surface--light .settings-section-nav__item:hover,
        .settings-surface--light .settings-section-nav__item--active {
          color: #0f1720;
          background: rgba(26, 113, 102, 0.08);
        }

        .settings-section-nav__item svg {
          height: 1.1rem;
          width: 1.1rem;
          color: currentColor;
        }

        .settings-stack {
          display: grid;
          gap: 1rem;
        }

        .settings-panel {
          scroll-margin-top: 6rem;
          border: 1px solid rgba(135, 164, 184, 0.32);
          border-radius: 8px;
          background: rgba(11, 21, 29, 0.72);
          padding: 1.35rem;
          box-shadow: 0 20px 44px rgba(0, 0, 0, 0.14);
          backdrop-filter: blur(18px);
        }

        .settings-panel--compact {
          padding: 1.15rem 1.35rem;
        }

        .settings-surface--light .settings-panel {
          background: rgba(255, 255, 255, 0.82);
          border-color: rgba(148, 163, 184, 0.42);
          box-shadow: 0 18px 36px rgba(15, 23, 42, 0.08);
        }

        .settings-panel__title {
          color: #f7fbfa;
          font-size: 1.02rem;
          font-weight: 700;
          line-height: 1.2;
        }

        .settings-surface--light .settings-panel__title {
          color: #111827;
        }

        .settings-info-grid,
        .settings-choice-grid,
        .settings-identity-grid,
        .settings-goal-grid {
          display: grid;
          gap: 0.75rem;
        }

        .settings-info-grid {
          grid-template-columns: repeat(1, minmax(0, 1fr));
        }

        .settings-info-value {
          margin-top: 0.65rem;
          overflow-wrap: anywhere;
          color: #f8fcfb;
          font-size: 1rem;
          font-weight: 700;
        }

        .settings-surface--light .settings-info-value {
          color: #111827;
        }

        .settings-input-shell {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          min-height: 3.1rem;
          border: 1px solid rgba(135, 164, 184, 0.36);
          border-radius: 7px;
          background: rgba(8, 16, 24, 0.5);
          padding: 0 0.85rem;
        }

        .settings-surface--light .settings-input-shell {
          background: rgba(255, 255, 255, 0.86);
          border-color: rgba(148, 163, 184, 0.42);
        }

        .settings-input,
        .settings-number-input {
          width: 100%;
          min-width: 0;
          border: 0;
          background: transparent;
          color: #fff;
          font-size: 0.95rem;
          font-weight: 650;
          outline: none;
        }

        .settings-number-input {
          height: 3.1rem;
          border: 1px solid rgba(135, 164, 184, 0.36);
          border-radius: 7px;
          background: rgba(8, 16, 24, 0.5);
          padding: 0 0.9rem;
        }

        .settings-surface--light .settings-input,
        .settings-surface--light .settings-number-input {
          color: #111827;
        }

        .settings-surface--light .settings-number-input {
          background: rgba(255, 255, 255, 0.86);
          border-color: rgba(148, 163, 184, 0.42);
        }

        .settings-check {
          color: rgba(148, 163, 184, 0.62);
        }

        .settings-check--valid {
          color: #4ee0c8;
        }

        .settings-handle {
          display: inline-flex;
          margin-top: 0.85rem;
          border-radius: 6px;
          background: rgba(255, 255, 255, 0.07);
          padding: 0.45rem 0.65rem;
          color: #fff;
          font-size: 1.12rem;
          font-weight: 750;
        }

        .settings-surface--light .settings-handle {
          background: rgba(15, 23, 42, 0.08);
          color: #111827;
        }

        .settings-primary-button,
        .settings-danger-button {
          display: inline-flex;
          min-height: 2.75rem;
          align-items: center;
          justify-content: center;
          border-radius: 5px;
          padding: 0 1.05rem;
          font-size: 0.82rem;
          font-weight: 800;
          transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease, opacity 0.16s ease;
        }

        .settings-primary-button {
          background: linear-gradient(135deg, #1a9a87 0%, #1a6c63 100%);
          color: #fff;
        }

        .settings-primary-button:hover {
          background: linear-gradient(135deg, #21b5a0 0%, #1b7a6f 100%);
        }

        .settings-primary-button:disabled,
        .settings-danger-button:disabled {
          cursor: not-allowed;
          opacity: 0.58;
        }

        .settings-danger-button {
          border: 1px solid rgba(255, 92, 108, 0.72);
          color: #ff8c96;
        }

        .settings-danger-button:hover {
          background: rgba(255, 92, 108, 0.08);
        }

        .settings-choice {
          min-height: 5.45rem;
          border: 1px solid rgba(135, 164, 184, 0.32);
          border-radius: 8px;
          background: rgba(7, 15, 23, 0.42);
          padding: 1rem;
          text-align: left;
          transition: background-color 0.16s ease, border-color 0.16s ease;
        }

        .settings-choice:hover {
          background: rgba(18, 33, 45, 0.58);
        }

        .settings-choice--active {
          border-color: #42d6bf;
          background: rgba(42, 190, 167, 0.08);
        }

        .settings-choice:disabled {
          cursor: not-allowed;
          opacity: 0.62;
        }

        .settings-surface--light .settings-choice {
          background: rgba(255, 255, 255, 0.76);
          border-color: rgba(148, 163, 184, 0.42);
        }

        .settings-surface--light .settings-choice:hover {
          background: #fff;
        }

        .settings-surface--light .settings-choice--active {
          background: rgba(26, 113, 102, 0.08);
          border-color: #248677;
        }

        .settings-choice__row {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 0.8rem;
        }

        .settings-choice__content {
          display: flex;
          min-width: 0;
          gap: 0.8rem;
        }

        .settings-choice__icon {
          color: #55dcc6;
        }

        .settings-surface--light .settings-choice__icon {
          color: #17695f;
        }

        .settings-choice__title {
          display: block;
          color: #fff;
          font-size: 0.9rem;
          font-weight: 800;
          line-height: 1.2;
        }

        .settings-choice__description {
          display: block;
          margin-top: 0.45rem;
          color: #aebdca;
          font-size: 0.8rem;
          line-height: 1.55;
        }

        .settings-surface--light .settings-choice__title {
          color: #111827;
        }

        .settings-surface--light .settings-choice__description {
          color: #52616f;
        }

        .settings-radio {
          display: flex;
          flex-shrink: 0;
          height: 1.1rem;
          width: 1.1rem;
          align-items: center;
          justify-content: center;
          border: 1px solid rgba(135, 164, 184, 0.5);
          border-radius: 999px;
        }

        .settings-radio__dot {
          height: 0.55rem;
          width: 0.55rem;
          border-radius: 999px;
          background: #54dfc8;
        }

        .settings-goal-grid {
          align-items: stretch;
        }

        .settings-goal-count {
          margin-top: 0.8rem;
          color: #fff;
          font-size: clamp(1.35rem, 3vw, 1.65rem);
          font-weight: 650;
        }

        .settings-surface--light .settings-goal-count {
          color: #111827;
        }

        .settings-ring-number {
          color: #fff;
          font-size: 1.35rem;
          font-weight: 800;
          letter-spacing: -0.03em;
        }

        .settings-surface--light .settings-ring-number {
          color: #111827;
        }

        .settings-progress-cell {
          display: flex;
          min-height: 8.5rem;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          border-left: 1px solid rgba(135, 164, 184, 0.2);
        }

        .settings-session-row {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .settings-message {
          border: 1px solid rgba(135, 164, 184, 0.28);
          border-radius: 7px;
          padding: 0.75rem 0.85rem;
          color: #c9d6df;
          font-size: 0.85rem;
          line-height: 1.5;
        }

        .settings-message--warning {
          border-color: rgba(245, 158, 11, 0.34);
          background: rgba(245, 158, 11, 0.08);
          color: #f8d18a;
        }

        .settings-security-note {
          display: flex;
          gap: 0.45rem;
          align-items: flex-start;
          color: #aebdca;
          font-size: 0.72rem;
          line-height: 1.55;
        }

        .settings-security-note svg {
          margin-top: 0.05rem;
          height: 0.95rem;
          width: 0.95rem;
          flex-shrink: 0;
        }

        .settings-surface--light .settings-security-note {
          color: #52616f;
        }

        @media (min-width: 640px) {
          .settings-summary-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
          }

          .settings-info-grid,
          .settings-choice-grid--two,
          .settings-identity-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .settings-choice-grid--three {
            grid-template-columns: repeat(3, minmax(0, 1fr));
          }

          .settings-session-row {
            flex-direction: row;
            align-items: center;
            justify-content: space-between;
          }
        }

        @media (min-width: 1024px) {
          .settings-surface {
            margin: -2rem -2.5rem -2rem;
            padding: 2.6rem 2.5rem 4rem;
          }

          .settings-hero {
            grid-template-columns: minmax(0, 1fr) minmax(26rem, 31rem);
            align-items: end;
          }

          .settings-layout {
            grid-template-columns: 15.5rem minmax(0, 1fr);
            align-items: start;
          }

          .settings-section-nav {
            position: sticky;
            top: 6.25rem;
          }

          .settings-goal-grid {
            grid-template-columns: minmax(9.5rem, 11rem) minmax(0, 1fr) 9.5rem;
          }
        }
      `} />
    </div>
  )
}

function modeLabel(mode: string) {
  return MODES.find((item) => item.value === mode)?.label ?? "Casual"
}

function SettingsStyles({ css }: { css: string }) {
  useEffect(() => {
    const styleId = "lorevia-settings-page-styles"
    if (document.getElementById(styleId)) return
    const style = document.createElement("style")
    style.id = styleId
    style.textContent = css
    document.head.appendChild(style)
    return () => {
      style.remove()
    }
  }, [css])

  return null
}

function SettingsPanel({ id, title, compact = false, children }: { id: string; title: string; compact?: boolean; children: ReactNode }) {
  return (
    <section id={id} className={compact ? "settings-panel settings-panel--compact" : "settings-panel"}>
      <h2 className="settings-panel__title">{title}</h2>
      <div className={compact ? "mt-3" : "mt-5"}>{children}</div>
    </section>
  )
}

function SummaryCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="settings-panel settings-panel--compact">
      <div className="flex items-center gap-3">
        <span className="settings-choice__icon">{icon}</span>
        <div>
          <p className="settings-label">{label}</p>
          <p className="settings-info-value">{value}</p>
        </div>
      </div>
    </div>
  )
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="settings-label">{label}</p>
      <p className="settings-info-value">{value}</p>
    </div>
  )
}

function SelectableCard({
  active,
  title,
  description,
  icon,
  disabled = false,
  onClick,
}: {
  active: boolean
  title: string
  description: string
  icon: ReactNode
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} disabled={disabled} className={active ? "settings-choice settings-choice--active" : "settings-choice"}>
      <span className="settings-choice__row">
        <span className="settings-choice__content">
          <span className="settings-choice__icon">{icon}</span>
          <span>
            <span className="settings-choice__title">{title}</span>
            <span className="settings-choice__description">{description}</span>
          </span>
        </span>
        <span className="settings-radio">{active ? <span className="settings-radio__dot" /> : null}</span>
      </span>
    </button>
  )
}

function InlineMessage({ message, tone, className = "" }: { message: string; tone: "warning" | "neutral"; className?: string }) {
  return <div className={`settings-message ${tone === "warning" ? "settings-message--warning" : ""} ${className}`.trim()}>{message}</div>
}

function GoalRing({ progress }: { progress: number }) {
  const circumference = 2 * Math.PI * 34
  const dashOffset = circumference - (progress / 100) * circumference

  return (
    <div className="relative mt-3 flex h-28 w-28 items-center justify-center">
      <svg className="h-28 w-28 -rotate-90" viewBox="0 0 84 84" aria-hidden="true">
        <circle cx="42" cy="42" r="34" fill="none" stroke="rgba(148, 163, 184, 0.22)" strokeWidth="8" />
        <circle
          cx="42"
          cy="42"
          r="34"
          fill="none"
          stroke="#54dfc8"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="absolute text-center">
        <p className="settings-ring-number">{progress}%</p>
        <p className="text-xs text-slate-400">of goal</p>
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

function PrivacyIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l7 3v5c0 4.5-2.7 7.5-7 9-4.3-1.5-7-4.5-7-9V7l7-3z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.5 12.5l1.6 1.6 3.4-3.4" />
    </svg>
  )
}

function MailIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 7.5A2.5 2.5 0 016.5 5h11A2.5 2.5 0 0120 7.5v9a2.5 2.5 0 01-2.5 2.5h-11A2.5 2.5 0 014 16.5v-9z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 7l7 5 7-5" />
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

function ShieldIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l7 3v5c0 4.5-2.7 7.5-7 9-4.3-1.5-7-4.5-7-9V7l7-3z" />
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
