"use client"
import { useState } from "react"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { authApi } from "@/lib/api/auth"
import { billingApi } from "@/lib/api/billing"

const MODES = [
  { value: "casual", label: "Casual", desc: "Quick summaries and light-touch guidance." },
  { value: "analyst", label: "Analyst", desc: "Deeper context and richer breakdowns." },
  { value: "speed", label: "Speed", desc: "Minimal output for fast reading sessions." },
]

export default function SettingsPage() {
  const { user, setUser, logout } = useAuthStore()
  const { theme, setTheme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [billingBusy, setBillingBusy] = useState(false)
  const [billingMessage, setBillingMessage] = useState<string | null>(null)

  const changeMode = async (mode: string) => {
    await authApi.setReadingMode(mode)
    if (user) setUser({ ...user, reading_mode: mode as any })
  }

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {}
    logout()
    if (typeof window !== "undefined") {
      window.location.href = "/login"
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

  return (
    <div className="space-y-6">
      <section className={`rounded-[2rem] border p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] ${
        isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/85"
      }`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-200" : "text-amber-700"}`}>Settings</p>
        <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-stone-900"}`}>Personalize the workspace</h1>
        <p className={`mt-3 max-w-2xl text-sm leading-6 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
          Keep your reading environment consistent across sessions, tune how much detail you want, and manage billing from one place.
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className={`rounded-[1.75rem] border p-6 ${
          isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/85"
        }`}>
          <h2 className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Account</h2>
          <div className="mt-4 space-y-2">
            <p className={isDark ? "text-sm text-gray-300" : "text-sm text-stone-600"}>Email: <span className="font-medium">{user?.email}</span></p>
            <p className={isDark ? "text-sm text-gray-300" : "text-sm text-stone-600"}>Plan: <span className="font-medium capitalize">{user?.tier ?? "free"}</span></p>
          </div>
          <p className={`mt-5 text-sm ${isDark ? "text-gray-300" : "text-stone-600"}`}>
            Manage your subscription in Paddle. Upgrades still happen from the pricing page, while payment method changes and cancellations live in the portal.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              onClick={openBillingPortal}
              disabled={billingBusy}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${isDark ? "border border-white/10 bg-white/10 text-white hover:bg-white/15" : "border border-stone-300 bg-white text-stone-900 hover:bg-stone-50"} disabled:opacity-60`}
            >
              {billingBusy ? "Opening billing..." : "Open billing portal"}
            </button>
          </div>
          {billingMessage ? (
            <div className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-amber-300/30 bg-amber-300/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
              {billingMessage}
            </div>
          ) : null}
        </section>

        <section className={`rounded-[1.75rem] border p-6 ${
          isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/85"
        }`}>
          <h2 className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Appearance</h2>
          <p className={`mt-2 text-sm ${isDark ? "text-gray-300" : "text-stone-600"}`}>Your theme is saved automatically, including the reader.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[
              { value: "light", label: "Light", desc: "Warm paper tones and bright cards." },
              { value: "dark", label: "Dark", desc: "Low-glare contrast for long sessions." },
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => setTheme(option.value as "light" | "dark")}
                className={`rounded-2xl border p-4 text-left transition ${
                  theme === option.value
                    ? isDark
                      ? "border-amber-300 bg-amber-300/10"
                      : "border-stone-900 bg-stone-900 text-white"
                    : isDark
                      ? "border-white/10 hover:bg-white/5"
                      : "border-stone-200 hover:bg-stone-50"
                }`}
              >
                <p className="text-sm font-semibold">{option.label}</p>
                <p className={`mt-1 text-xs leading-5 ${
                  theme === option.value ? (isDark ? "text-amber-100" : "text-white/80") : isDark ? "text-gray-400" : "text-stone-500"
                }`}>
                  {option.desc}
                </p>
              </button>
            ))}
          </div>
        </section>
      </div>

      <section className={`rounded-[1.75rem] border p-6 ${
        isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/85"
      }`}>
        <h2 className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Reading mode</h2>
        <div className="mt-4 grid gap-3">
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => changeMode(m.value)}
              className={`rounded-2xl border p-4 text-left transition ${
                user?.reading_mode === m.value
                  ? isDark
                    ? "border-amber-300 bg-amber-300/10"
                    : "border-stone-900 bg-stone-900 text-white"
                  : isDark
                    ? "border-white/10 hover:bg-white/5"
                    : "border-stone-200 hover:bg-stone-50"
              }`}
            >
              <p className="text-sm font-semibold">{m.label}</p>
              <p className={`mt-1 text-xs ${
                user?.reading_mode === m.value ? (isDark ? "text-amber-100" : "text-white/80") : isDark ? "text-gray-400" : "text-stone-500"
              }`}>
                {m.desc}
              </p>
            </button>
          ))}
        </div>
      </section>

      <button
        onClick={handleLogout}
        className={`rounded-full px-4 py-2 text-sm transition ${
          isDark ? "text-rose-300 hover:bg-white/10" : "text-rose-600 hover:bg-white"
        }`}
      >
        Sign out
      </button>
    </div>
  )
}
