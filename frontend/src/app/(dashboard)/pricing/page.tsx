"use client"

import { useState } from "react"

import { billingApi } from "@/lib/api/billing"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

type BillingCycle = "monthly" | "annual"
type PaidPlanCode = "pro_monthly" | "pro_annual" | "power_monthly" | "power_annual"

type PricingTier = {
  name: string
  badge: string
  priceMonthly: number
  priceAnnual: number
  subtitle: string
  highlight: boolean
  cta: string
  monthlyCode: PaidPlanCode | null
  annualCode: PaidPlanCode | null
  message?: string | null
  bullets: string[]
}

const pricingTiers: PricingTier[] = [
  {
    name: "Starter",
    badge: "Foundation",
    priceMonthly: 0,
    priceAnnual: 0,
    subtitle: "Free forever",
    highlight: false,
    cta: "Get started",
    monthlyCode: null,
    annualCode: null,
    message: "Starter is already available inside the app.",
    bullets: [
      "Track up to 2 books",
      "Tap any character name to get their information",
      'Ask 5 questions per day ("When did they first meet?")',
      "Basic summaries and reading progress",
    ],
  },
  {
    name: "Reader",
    badge: "Most Popular",
    priceMonthly: 8,
    priceAnnual: 80,
    subtitle: "For the dedicated reader",
    highlight: false,
    cta: "Go Pro",
    monthlyCode: "pro_monthly",
    annualCode: "pro_annual",
    bullets: [
      "Everything in Starter, plus:",
      "Unlimited books",
      "Multi-mode Story Summaries",
      "Ask unlimited questions about your story",
      "Smarter predictions about plot and characters",
    ],
  },
  {
    name: "Author",
    badge: "Professional",
    priceMonthly: 24,
    priceAnnual: 240,
    subtitle: "For manuscript builders",
    highlight: true,
    cta: "Start Drafting",
    monthlyCode: "power_monthly",
    annualCode: "power_annual",
    bullets: [
      "Everything in Reader, plus:",
      "Catch continuity errors automatically",
      "Chapter & Manuscript feedback",
      "Auto-generated character reference sheets",
      "Edit and organize your full manuscript",
      "Visual character relationship maps",
    ],
  },
  {
    name: "Architect",
    badge: "Power User",
    priceMonthly: 36,
    priceAnnual: 360,
    subtitle: "For series & world-builders",
    highlight: false,
    cta: "Build your World",
    monthlyCode: null,
    annualCode: null,
    message: "Architect tier is not checkout-enabled in this app environment yet.",
    bullets: [
      "Everything in Author, plus:",
      "Faster processing for big files",
      "Deeper continuity analysis",
      "Analyze multiple books together",
      "Early access to new features",
    ],
  },
]

export default function PricingPage() {
  const { theme } = usePreferencesStore()
  const { user } = useAuthStore()
  const isDark = theme === "dark"
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function handlePlanClick(tier: PricingTier) {
    const selectedPlanCode = billingCycle === "annual" ? tier.annualCode : tier.monthlyCode
    if (!selectedPlanCode) {
      setMessage(tier.message ?? `${tier.name} cannot be started from this page yet.`)
      return
    }

    setBusyPlan(selectedPlanCode)
    setMessage(null)
    try {
      const result = await billingApi.checkout(selectedPlanCode)
      if (!result.billing_enabled || !result.checkout_url) {
        setMessage(result.message ?? "Billing is not configured in this environment yet.")
        return
      }
      window.location.href = result.checkout_url
    } catch {
      setMessage("We could not start checkout right now. Please try again in a moment.")
    } finally {
      setBusyPlan(null)
    }
  }

  return (
    <div className={`rounded-[2.2rem] border px-6 py-8 shadow-[0_30px_110px_-55px_rgba(15,23,42,0.4)] md:px-8 lg:px-10 ${isDark ? "border-white/10 bg-[#050505]" : "border-stone-200 bg-[#0c0c0d] text-white"}`}>
      <div className="flex flex-col gap-10 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-[0.34em] text-slate-300">Pricing</p>
          <h1 className="mt-4 font-serif text-5xl leading-[0.95] text-white md:text-6xl">
            Pick a tier that matches your
            <br />
            pace.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-9 text-slate-300">
            Monthly billing is shown by default. Every new signup gets 10 days of Author Pro access — no credit card required.
          </p>
          {user ? (
            <p className="mt-4 text-sm text-slate-500">Your account is ready for upgrades right from this screen.</p>
          ) : null}
        </div>

        <div className="flex justify-start lg:justify-end">
          <div className="relative inline-flex items-center rounded-full bg-white/10 p-1">
            <div
              className="absolute left-1 top-1 h-[calc(100%-8px)] w-[calc(50%-4px)] rounded-full bg-white transition-transform duration-300 ease-out"
              style={{ transform: billingCycle === "annual" ? "translateX(100%)" : "translateX(0)" }}
            />
            <button
              type="button"
              onClick={() => setBillingCycle("monthly")}
              className={`relative z-10 rounded-full px-5 py-2 text-sm font-semibold transition-colors duration-200 ${
                billingCycle === "monthly" ? "text-stone-950" : "text-slate-300 hover:text-white"
              }`}
            >
              Monthly
            </button>
            <button
              type="button"
              onClick={() => setBillingCycle("annual")}
              className={`relative z-10 rounded-full px-5 py-2 text-sm font-semibold transition-colors duration-200 ${
                billingCycle === "annual" ? "text-stone-950" : "text-slate-300 hover:text-white"
              }`}
            >
              Annual
            </button>
          </div>
        </div>
      </div>

      {message ? (
        <div className="mt-6 rounded-2xl border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
          {message}
        </div>
      ) : null}

      <div className="mt-16 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {pricingTiers.map((tier) => {
          const price = billingCycle === "annual" ? tier.priceAnnual : tier.priceMonthly
          const unit = tier.name === "Starter" ? "" : billingCycle === "annual" ? "/yr" : "/mo"
          const selectedPlanCode = billingCycle === "annual" ? tier.annualCode : tier.monthlyCode
          const isBusy = selectedPlanCode ? busyPlan === selectedPlanCode : false

          return (
            <article
              key={tier.name}
              className={`group relative flex min-h-[48rem] flex-col rounded-[2rem] p-8 transition-all duration-300 hover:-translate-y-1 ${
                tier.highlight
                  ? "border border-violet-400/20 bg-violet-500/[0.07] shadow-[inset_0_0_40px_rgba(139,92,246,0.10),0_24px_80px_-30px_rgba(139,92,246,0.18)]"
                  : "border border-white/10 bg-white/[0.03] hover:border-white/15"
              }`}
            >
              <div className="mb-8 flex items-center justify-between">
                <span className={`text-[10px] font-bold uppercase tracking-[0.2em] ${tier.highlight ? "text-violet-300" : "text-slate-500"}`}>
                  {tier.badge}
                </span>
                {tier.highlight ? <div className="h-2.5 w-2.5 rounded-full bg-violet-300" /> : null}
              </div>

              <h2 className="text-2xl font-semibold text-white">{tier.name}</h2>

              <div className="mt-4 flex items-end gap-1">
                <span className="text-6xl font-bold tracking-tighter text-white">
                  {tier.name === "Starter" ? "$0" : `$${price}`}
                </span>
                <span className="mb-2 text-sm text-slate-400">{unit}</span>
              </div>

              <p className="mt-2 text-sm text-slate-400">{tier.subtitle}</p>

              <ul className="mt-10 space-y-5">
                {tier.bullets.map((bullet) => (
                  <li key={bullet} className="flex items-start gap-4 text-sm leading-8">
                    <span className={`mt-1 text-base font-bold ${tier.highlight ? "text-violet-300" : "text-slate-500"}`}>•</span>
                    <span className={bullet.startsWith("Everything in") ? "text-slate-400" : "text-slate-200"}>{bullet}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-auto pt-10">
                <button
                  type="button"
                  onClick={() => void handlePlanClick(tier)}
                  disabled={isBusy}
                  className={`inline-flex w-full items-center justify-center rounded-xl py-4 text-base font-semibold transition-all duration-200 disabled:opacity-60 ${
                    tier.highlight
                      ? "bg-white text-stone-950 hover:bg-stone-100"
                      : "border border-white/10 bg-transparent text-slate-100 hover:border-white/20 hover:bg-white/[0.04]"
                  }`}
                >
                  {isBusy ? "Opening checkout..." : tier.cta}
                </button>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}
