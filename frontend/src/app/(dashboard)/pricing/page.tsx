"use client"

import { useState } from "react"
import { billingApi } from "@/lib/api/billing"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

type BillingCycle = "monthly" | "yearly"
type PaidPlanCode = "pro_monthly" | "pro_annual" | "power_monthly" | "power_annual"

const plans = [
  {
    name: "Starter",
    monthly: "$0",
    yearly: "$0",
    note: "Read with the core workspace",
    monthlyCode: null,
    yearlyCode: null,
    highlight: "Best for trying LoreVia",
    comingSoon: "Lore Score, streaks, and limited unlockables",
    bullets: ["Spoiler-safe reading workspace", "Chapter memory, summaries, and recall", "A strong baseline for trying LoreVia"],
  },
  {
    name: "Pro",
    monthly: "$9",
    yearly: "$90",
    note: "For committed readers",
    monthlyCode: "pro_monthly" as PaidPlanCode,
    yearlyCode: "pro_annual" as PaidPlanCode,
    highlight: "Best for serious readers",
    comingSoon: "Deeper series intelligence and richer assistive reading",
    bullets: ["More summaries, search, and grounded Q&A", "Expanded continuity across longer books", "Better headroom for regular reading"],
  },
  {
    name: "Power",
    monthly: "$17",
    yearly: "$170",
    note: "For dense books and long reading arcs",
    monthlyCode: "power_monthly" as PaidPlanCode,
    yearlyCode: "power_annual" as PaidPlanCode,
    highlight: "Best for dense books and long libraries",
    comingSoon: "Cross-book mastery, alerts, and advanced character systems",
    bullets: ["Deepest workspace for long books", "Highest interaction capacity", "Best fit for classics, fantasy, and rereads"],
  },
]

export default function PricingPage() {
  const { theme } = usePreferencesStore()
  const { user } = useAuthStore()
  const isDark = theme === "dark"
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function handlePlanClick(planCode: PaidPlanCode | null) {
    if (!planCode) {
      setMessage("Starter is already available in the app.")
      return
    }

    setBusyPlan(planCode)
    setMessage(null)
    try {
      const result = await billingApi.checkout(planCode)
      if (!result.billing_enabled || !result.checkout_url) {
        setMessage(result.message ?? "Billing is not configured in this environment yet.")
        return
      }
      window.location.href = result.checkout_url
    } catch {
      setMessage("We could not start Paddle checkout right now. Please try again in a moment.")
    } finally {
      setBusyPlan(null)
    }
  }

  return (
    <div className="space-y-8">
      <section className={`rounded-[2rem] border p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.32)] ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/90"}`}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-200" : "text-amber-700"}`}>Pricing</p>
            <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-slate-950"}`}>Choose the reading workspace that matches your pace and depth.</h1>
            <p className={`mt-3 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
              Starter keeps the core experience open. Pro and Power expand continuity, interaction depth, and room for longer projects.
            </p>
          </div>
          <div className={`inline-flex rounded-full border p-1 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-slate-100"}`}>
            {(["monthly", "yearly"] as BillingCycle[]).map((cycle) => (
              <button
                key={cycle}
                onClick={() => setBillingCycle(cycle)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  billingCycle === cycle
                    ? isDark ? "bg-white text-slate-950" : "bg-white text-slate-950 shadow-sm"
                    : isDark ? "text-slate-300" : "text-slate-600"
                }`}
              >
                {cycle === "monthly" ? "Monthly" : "Yearly"}
              </button>
            ))}
          </div>
        </div>
        {message ? (
          <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${isDark ? "border-amber-300/30 bg-amber-300/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
            {message}
          </div>
        ) : null}
      </section>

      <div className="grid gap-5 lg:grid-cols-3">
        {plans.map((plan) => {
          const active = plan.name === "Pro"
          const selectedPrice = billingCycle === "yearly" ? plan.yearly : plan.monthly
          const selectedPlanCode = billingCycle === "yearly" ? plan.yearlyCode : plan.monthlyCode

          return (
            <article key={plan.name} className={`rounded-[2rem] border p-6 ${active ? "bg-slate-950 text-white shadow-[0_32px_100px_-56px_rgba(15,23,42,0.52)]" : isDark ? "border-white/10 bg-white/5 text-white" : "border-slate-200 bg-white text-slate-900 shadow-[0_18px_70px_-55px_rgba(15,23,42,0.18)]"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${active ? "text-amber-200" : isDark ? "text-slate-400" : "text-slate-500"}`}>{plan.highlight}</p>
              <div className="mt-4 flex items-end gap-3">
                <h2 className="font-serif text-4xl">{plan.name}</h2>
                <p className={`${active ? "text-slate-300" : isDark ? "text-slate-400" : "text-slate-500"}`}>{selectedPrice}</p>
              </div>
              <p className={`mt-1 text-xs uppercase tracking-[0.18em] ${active ? "text-slate-400" : isDark ? "text-slate-500" : "text-slate-400"}`}>
                {billingCycle === "yearly" ? "per year" : "per month"} - {plan.note}
              </p>
              <ul className="mt-6 space-y-3">
                {plan.bullets.map((bullet) => (
                  <li key={bullet} className={`rounded-2xl px-4 py-3 text-sm ${active ? "bg-white/8 text-slate-100" : isDark ? "bg-white/10 text-slate-200" : "bg-slate-100 text-slate-700"}`}>
                    {bullet}
                  </li>
                ))}
              </ul>
              <div className={`mt-5 rounded-2xl border px-4 py-3 text-sm ${active ? "border-white/10 bg-white/6 text-slate-200" : isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
                <span className={`mr-2 inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${active ? "bg-amber-300 text-slate-950" : isDark ? "bg-white text-slate-950" : "bg-slate-950 text-white"}`}>
                  Coming soon
                </span>
                {plan.comingSoon}
              </div>
              {selectedPlanCode ? (
                <button
                  onClick={() => handlePlanClick(selectedPlanCode)}
                  disabled={busyPlan === selectedPlanCode}
                  className={`mt-7 w-full rounded-full px-5 py-3 text-sm font-semibold transition ${active ? "bg-amber-300 text-slate-950 hover:bg-amber-200" : isDark ? "border border-white/10 bg-white/10 text-white hover:bg-white/15" : "border border-slate-300 bg-white text-slate-900 hover:bg-slate-50"} disabled:opacity-60`}
                >
                  {busyPlan === selectedPlanCode ? "Opening checkout..." : `Choose ${plan.name}`}
                </button>
              ) : (
                <div className={`mt-7 rounded-full border px-5 py-3 text-center text-sm font-semibold ${isDark ? "border-white/10 text-slate-200" : "border-slate-300 text-slate-600"}`}>
                  Current plan
                </div>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
