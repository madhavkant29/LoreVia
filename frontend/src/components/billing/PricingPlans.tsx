"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { billingApi } from "@/lib/api/billing"
import type { PaidPlanCode } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"

type BillingCycle = "monthly" | "annual"

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

type PricingPlansProps = {
  surface?: "public" | "app"
}

const pricingTiers: PricingTier[] = [
  {
    name: "Free",
    badge: "After trial",
    priceMonthly: 0,
    priceAnnual: 0,
    subtitle: "Free forever after your Author trial",
    highlight: false,
    cta: "Get started",
    monthlyCode: null,
    annualCode: null,
    message: "Free is already available inside the app.",
    bullets: [
      "2 active books",
      "Unlimited Smart Tap and memory recall",
      "Full character profiles",
      "Short summaries only",
      "5 semantic searches/day and 3 prediction queries/day",
    ],
  },
  {
    name: "Reader",
    badge: "Most popular",
    priceMonthly: 12,
    priceAnnual: 120,
    subtitle: "For the dedicated reader",
    highlight: false,
    cta: "Go Reader",
    monthlyCode: "reader_monthly",
    annualCode: "reader_annual",
    bullets: [
      "Everything in Free, plus:",
      "Unlimited books",
      "All 3 summary modes",
      "Unlimited semantic search",
      "10 prediction queries/day",
      "Reader-only by design: no authoring tools",
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
    monthlyCode: "author_monthly",
    annualCode: "author_annual",
    bullets: [
      "Everything in Reader, plus:",
      "Catch continuity errors automatically",
      "Chapter and full-book manuscript editing",
      "Character bible export and edit mode",
      "Visual character relationship maps",
      "Marketed as unlimited with a 30/day fair-use cap",
    ],
  },
  {
    name: "Lore Architect",
    badge: "Power user",
    priceMonthly: 36,
    priceAnnual: 360,
    subtitle: "For series and world-builders",
    highlight: false,
    cta: "Build your World",
    monthlyCode: "architect_monthly",
    annualCode: "architect_annual",
    bullets: [
      "Everything in Author, plus:",
      "Priority processing planned for launch rollout",
      "Deeper continuity analysis",
      "Analyze multiple books together",
      "Early access to new features",
      "Marketed as unlimited with a 60/day fair-use cap",
    ],
  },
]

function getGuestCtaLabel(tier: PricingTier) {
  return tier.name === "Free" ? "Start free" : "Start free trial"
}

export function PricingPlans({ surface = "public" }: PricingPlansProps) {
  const router = useRouter()
  const { user } = useAuthStore()
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("annual")
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function handlePlanClick(tier: PricingTier) {
    if (!user) {
      router.push("/register")
      return
    }

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

  const helperCopy = user
    ? "Your account is ready for upgrades from this screen."
    : surface === "public"
      ? "Create an account to start the 10-day Author trial, then choose the plan that fits."
      : "Create an account or sign in before starting checkout."

  return (
    <section className={surface === "public" ? "border-t border-white/[0.08] py-8" : undefined}>
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-[-0.02em] text-[#F2F4F7]">Plans</h2>
          <p className="mt-2 text-sm text-[#7F8994]">{helperCopy}</p>
        </div>

        <div className="inline-flex w-fit rounded-full border border-white/[0.08] bg-[#0B0F14] p-1">
          {(["monthly", "annual"] as const).map((cycle) => (
            <button
              key={cycle}
              type="button"
              onClick={() => setBillingCycle(cycle)}
              className={`rounded-full px-4 py-2 text-sm font-medium capitalize transition ${
                billingCycle === cycle ? "bg-[#D2B47A] text-[#05070A]" : "text-[#A8B0BA] hover:text-[#F2F4F7]"
              }`}
            >
              {cycle}
            </button>
          ))}
        </div>
      </div>

      {message ? (
        <div className="mt-6 rounded-xl border border-[#C9A86A]/30 bg-[#0B0F14] px-4 py-3 text-sm leading-6 text-[#E5CA91]">
          {message}
        </div>
      ) : null}

      <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {pricingTiers.map((tier) => {
          const price = billingCycle === "annual" ? tier.priceAnnual : tier.priceMonthly
          const unit = tier.name === "Free" ? "" : billingCycle === "annual" ? "/yr" : "/mo"
          const selectedPlanCode = billingCycle === "annual" ? tier.annualCode : tier.monthlyCode
          const isBusy = selectedPlanCode ? busyPlan === selectedPlanCode : false
          const buttonLabel = user ? tier.cta : getGuestCtaLabel(tier)

          return (
            <article
              key={tier.name}
              className={`flex min-h-[34rem] flex-col rounded-xl border bg-[#0B0F14] p-6 ${
                tier.highlight ? "border-[#C9A86A]/55" : "border-white/[0.08]"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#7F8994]">{tier.badge}</p>
                  <h3 className="mt-4 text-2xl font-semibold text-[#F2F4F7]">{tier.name}</h3>
                </div>
                {tier.highlight ? <span className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#C9A86A]">Core</span> : null}
              </div>

              <div className="mt-7 flex items-end gap-1">
                <span className="text-5xl font-semibold tracking-[-0.05em] text-[#F2F4F7]">
                  {tier.name === "Free" ? "$0" : `$${price}`}
                </span>
                <span className="mb-1 text-sm text-[#7F8994]">{unit}</span>
              </div>

              <p className="mt-3 text-sm leading-6 text-[#A8B0BA]">{tier.subtitle}</p>

              <ul className="mt-8 space-y-3 text-sm leading-6 text-[#A8B0BA]">
                {tier.bullets.map((bullet) => (
                  <li key={bullet} className="flex gap-3">
                    <span className="text-[#C9A86A]" aria-hidden="true">
                      -
                    </span>
                    <span className={bullet.startsWith("Everything in") ? "text-[#7F8994]" : undefined}>{bullet}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-auto pt-8">
                <button
                  type="button"
                  onClick={() => void handlePlanClick(tier)}
                  disabled={isBusy}
                  className={`inline-flex w-full items-center justify-center rounded-lg border px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                    tier.highlight
                      ? "border-[#D2B47A] bg-[#D2B47A] text-[#05070A] hover:bg-[#E5CA91]"
                      : "border-white/[0.1] text-[#F2F4F7] hover:border-[#C9A86A]/45"
                  }`}
                >
                  {isBusy ? "Opening checkout..." : buttonLabel}
                </button>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
