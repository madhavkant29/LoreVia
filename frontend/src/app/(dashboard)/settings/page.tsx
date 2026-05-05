"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import {
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
} from "@/components/ui/Workspace"
import { authApi } from "@/lib/api/auth"
import { billingApi } from "@/lib/api/billing"
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
  const router = useRouter()

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
                <div className="app-chip">{user?.tier ?? "free"} plan</div>
                <div className="app-chip">{theme} theme</div>
              </div>
            }
          />
        </WorkspacePanel>

        <section className="grid gap-4 sm:grid-cols-3">
          <WorkspaceMetric
            label="Plan"
            value={(user?.tier ?? "free").toUpperCase()}
            note="Current workspace access level"
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
                  {user?.tier ?? "free"}
                </p>
              </div>
            </div>
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
