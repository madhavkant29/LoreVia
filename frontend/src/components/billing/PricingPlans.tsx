"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { billingApi } from "@/lib/api/billing"
import {
  pricingTierAccessLabel,
  pricingTierGuestCtaLabel,
  pricingTiers,
  type BillingCycle,
  type PricingTier,
} from "@/lib/billing/catalog"
import { useAuthStore } from "@/lib/stores/authStore"

type PricingPlansProps = {
  surface?: "public" | "app"
}

export function PricingPlans({ surface = "public" }: PricingPlansProps) {
  const router = useRouter()
  const { user } = useAuthStore()
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("annual")
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function handlePlanClick(tier: PricingTier) {
    if (tier.access === "free") {
      if (!user) {
        router.push("/register")
        return
      }

      setMessage("Free is included with every account. Paid checkout only applies to Author and Architect.")
      return
    }

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
    ? "Free is already included in your account. Only Author and Architect start paid checkout from this screen."
    : surface === "public"
      ? "Every signup starts with 10 days of Author access at no charge. After the trial, the account falls back to Free unless you upgrade to a paid plan for deeper manuscript intelligence."
      : "Free is included with every account. Sign in to upgrade to a paid plan."

  return (
    <section className={surface === "public" ? "border-t border-white/[0.08] py-8" : undefined}>
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-[-0.02em] text-[#F2F4F7]">Plans for fiction authors and complex story worlds</h2>
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

      <div className="mt-6 rounded-2xl border border-white/[0.08] bg-[#0B0F14] px-4 py-4 text-sm leading-6 text-[#C8D0D9]">
        <p>Every new account starts with 10 days of Author access and no credit card.</p>
        <p className="mt-2 text-[#A8B0BA]">After that, you keep the Free plan unless you choose a paid subscription for ongoing continuity and manuscript work.</p>
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
          const buttonLabel = user ? tier.cta : pricingTierGuestCtaLabel(tier)

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

              <p className="mt-5 text-xs font-semibold uppercase tracking-[0.2em] text-[#C9A86A]">
                {pricingTierAccessLabel(tier)}
              </p>

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

      <p className="mt-5 text-sm leading-6 text-[#7F8994]">
        Only Author and Architect are paid subscriptions. Free stays available without checkout.
      </p>
      <p className="mt-3 text-sm leading-6 text-[#7F8994]">
        Worldbuilding manuscripts count as uploads on every tier. On Author, a series-linked worldbuilding manuscript counts once per book in that series. Architect remains unlimited.
      </p>
    </section>
  )
}
