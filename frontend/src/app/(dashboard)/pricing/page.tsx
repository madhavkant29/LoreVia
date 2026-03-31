"use client"

import { useState } from "react"
import { billingApi } from "@/lib/api/billing"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const plans = [
  {
    name: "Starter",
    price: "$0",
    note: "Current baseline",
    planCode: null,
    bullets: ["Spoiler-safe reading workspace", "Character memory and recall", "A polished way to start reading with LoreVia"],
  },
  {
    name: "Pro",
    price: "$14",
    note: "per month",
    planCode: "pro_monthly" as const,
    bullets: ["Expanded reading capacity", "Richer continuity and advanced character detail", "More summaries, search, and grounded Q&A headroom"],
  },
  {
    name: "Power",
    price: "$29",
    note: "per month",
    planCode: "power_monthly" as const,
    bullets: ["Maximum workspace depth", "Best fit for long books, rereads, and serious projects", "Highest interaction and continuity capacity"],
  },
]

export default function PricingPage() {
  const user = useAuthStore((state) => state.user)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function handlePlanClick(planCode: "pro_monthly" | "power_monthly" | null) {
    if (!planCode) return
    setBusyPlan(planCode)
    setMessage(null)
    try {
      const result = await billingApi.checkout(planCode)
      if (!result.billing_enabled || !result.checkout_url) {
        setMessage(result.message ?? "Billing is not configured in this environment.")
        return
      }
      window.location.href = result.checkout_url
    } catch {
      setMessage("We could not start checkout right now.")
    } finally {
      setBusyPlan(null)
    }
  }

  async function openPortal() {
    setMessage(null)
    try {
      const result = await billingApi.portal()
      if (!result.billing_enabled || !result.portal_url) {
        setMessage(result.message ?? "Billing is not configured in this environment.")
        return
      }
      window.location.href = result.portal_url
    } catch {
      setMessage("We could not open billing right now.")
    }
  }

  return (
    <div className="space-y-8">
      <section className={`rounded-[2rem] border p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.32)] ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/90"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-200" : "text-amber-700"}`}>Pricing</p>
        <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-slate-950"}`}>Choose the workspace depth that matches your reading life.</h1>
        <p className={`mt-3 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
          Starter gives you the spoiler-aware core. Pro and Power expand continuity, interaction depth, and the amount of reading space you can grow into.
        </p>
        {user?.tier && user.tier !== "free" ? (
          <button
            onClick={openPortal}
            className={`mt-5 rounded-full px-4 py-2 text-sm font-medium transition ${isDark ? "border border-white/15 text-slate-200 hover:bg-white/10" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}
          >
            Manage billing
          </button>
        ) : null}
        {message ? <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{message}</div> : null}
      </section>

      <div className="grid gap-5 lg:grid-cols-3">
        {plans.map((plan) => {
          const active = plan.name.toLowerCase() === "pro"
          return (
            <article key={plan.name} className={`rounded-[2rem] border p-6 ${active ? "bg-slate-950 text-white shadow-[0_32px_100px_-56px_rgba(15,23,42,0.52)]" : isDark ? "border-white/10 bg-white/5 text-white" : "border-slate-200 bg-white text-slate-900 shadow-[0_18px_70px_-55px_rgba(15,23,42,0.18)]"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${active ? "text-amber-200" : isDark ? "text-slate-400" : "text-slate-500"}`}>{plan.note}</p>
              <div className="mt-4 flex items-end gap-3">
                <h2 className="font-serif text-4xl">{plan.name}</h2>
                <p className={`${active ? "text-slate-300" : isDark ? "text-slate-400" : "text-slate-500"}`}>{plan.price}</p>
              </div>
              <ul className="mt-6 space-y-3">
                {plan.bullets.map((bullet) => (
                  <li key={bullet} className={`rounded-2xl px-4 py-3 text-sm ${active ? "bg-white/8 text-slate-100" : isDark ? "bg-white/10 text-slate-200" : "bg-slate-100 text-slate-700"}`}>
                    {bullet}
                  </li>
                ))}
              </ul>
              {plan.planCode ? (
                <button
                  onClick={() => handlePlanClick(plan.planCode)}
                  disabled={busyPlan === plan.planCode}
                  className={`mt-7 w-full rounded-full px-5 py-3 text-sm font-semibold transition ${active ? "bg-amber-300 text-slate-950 hover:bg-amber-200" : "border border-slate-300 bg-white text-slate-900 hover:bg-slate-50"} disabled:opacity-60`}
                >
                  {busyPlan === plan.planCode ? "Opening checkout..." : `Choose ${plan.name}`}
                </button>
              ) : (
                <div className={`mt-7 rounded-full px-5 py-3 text-center text-sm font-semibold ${isDark ? "border border-white/10 text-slate-300" : "border border-slate-300 text-slate-600"}`}>
                  {user?.tier === "free" ? "Current plan" : "Available by default"}
                </div>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
