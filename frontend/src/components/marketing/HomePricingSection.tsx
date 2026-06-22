"use client"

import Link from "next/link"
import type { Route } from "next"
import { useState } from "react"

import { Reveal } from "@/components/marketing/Reveal"
import {
  pricingTierAccessLabel,
  pricingTierAnnualSavings,
  pricingTierPrice,
  pricingTierPriceSuffix,
  pricingTiers,
  type BillingCycle,
} from "@/lib/billing/catalog"

type HomePricingSectionProps = {
  ctaHref: Route
}

const marketingPricingContent = pricingTiers.map((tier) => ({
  ...tier,
  subtitle:
    tier.name === "Free"
      ? "For keeping access after the trial."
      : tier.name === "Author"
        ? "For active drafting, revision, and continuity work."
        : "For series, worldbuilding, and multi-book continuity.",
  bullets:
    tier.name === "Free"
      ? [
          "Read existing projects",
          "Export manuscript and novel files",
          "1 Story Advisor turn per week",
          "Join invited beta reads",
          "Author tools only during the trial",
        ]
      : tier.name === "Author"
        ? [
            "Everything in Free",
            "2M active words and 1M processed words monthly",
            "5 GB source storage",
            "30 Story Advisor turns per day",
            "30 continuity and editorial scans per day",
            "Manuscript editor, notes, summaries, and search",
          ]
        : [
            "Everything in Author",
            "8M active words and 4M processed words monthly",
            "25 GB source storage",
            "60 Story Advisor turns per day",
            "60 continuity and editorial scans per day",
            "Multi-book continuity",
          ],
  cta: "Analyze my manuscript",
}))

export function HomePricingSection({ ctaHref }: HomePricingSectionProps) {
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")

  return (
    <section id="pricing" className="mx-auto max-w-7xl px-5 py-20 md:px-8">
      <div className="text-center">
        <p className="text-3xs font-semibold uppercase tracking-[0.32em] text-[#6fae9f]">Pricing</p>
        <h2 className="mt-5 font-display text-4xl font-semibold leading-[1.02] text-white md:text-5xl">
          Simple, transparent pricing
        </h2>
        <p className="mx-auto mt-5 max-w-3xl text-lg leading-8 text-[#aeb9b3]">
          Every signup starts with a 10-day Author trial at no charge. Free stays available after that, and Author remains the main plan for active manuscript work.
        </p>
      </div>

      <div className="mt-8 flex justify-center">
        <div className="inline-flex items-center rounded-full border border-white/10 bg-white/5 p-1.5">
          {(["monthly", "annual"] as const).map((cycle) => (
            <button
              key={cycle}
              type="button"
              onClick={() => setBillingCycle(cycle)}
              className={`rounded-full px-5 py-2.5 text-sm font-semibold transition ${
                billingCycle === cycle
                  ? "bg-[#1f615d] text-white"
                  : "text-[#aeb9b3] hover:text-white"
              }`}
            >
              {cycle === "annual" ? "Yearly" : "Monthly"}
            </button>
          ))}
        </div>
      </div>

      <p className="mt-5 text-center text-sm text-[#8fa19a]">
        Includes a 10-day Author trial. No payment required.
      </p>

      <div className="mt-10 grid gap-5 xl:grid-cols-3">
        {marketingPricingContent.map((tier, index) => {
          const price = pricingTierPrice(tier, billingCycle)
          const suffix = pricingTierPriceSuffix(tier, billingCycle)
          const savings = billingCycle === "annual" ? pricingTierAnnualSavings(tier) : 0

          return (
            <Reveal key={tier.name} delay={index * 70} className="h-full">
              <article
                className={`relative flex h-full flex-col rounded-lg border p-6 md:p-7 ${
                  tier.highlight
                    ? "border-[#205f58] bg-[#11312d]"
                    : "border-white/10 bg-[#0d1715]"
                }`}
              >
                {tier.highlight ? (
                  <div className="absolute right-6 top-6 rounded-full border border-[#2d756c] bg-[#143632] px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#86decd]">
                    Most popular
                  </div>
                ) : null}

                <div className="min-h-[9rem]">
                  <h3 className="text-2xl font-semibold text-white">{tier.name}</h3>
                  <p className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-[#6fae9f]">
                    {pricingTierAccessLabel(tier)}
                  </p>
                  <p className="mt-4 text-sm leading-7 text-[#aeb9b3]">{tier.subtitle}</p>
                </div>

                <div className="mt-8 min-h-[5rem]">
                  <div className="flex items-end gap-2">
                    <span className="text-5xl font-semibold tracking-tight text-white">${price}</span>
                    {suffix ? <span className="pb-1 text-sm text-[#8fa19a]">{suffix}</span> : null}
                  </div>
                  {savings > 0 ? (
                    <p className="mt-3 text-sm font-medium text-[#86decd]">Save ${savings} with yearly billing</p>
                  ) : (
                    <div className="mt-3 h-[1.5rem]" aria-hidden="true" />
                  )}
                </div>

                <ul className="mt-8 flex-1 space-y-4 text-sm leading-7 text-[#d9e0db]">
                  {tier.bullets.map((bullet) => (
                    <li key={bullet} className="flex items-start gap-3">
                      <span className={tier.highlight ? "pt-0.5 text-[#86decd]" : "pt-0.5 text-[#6fae9f]"}>+</span>
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={ctaHref}
                  className={`mt-10 inline-flex w-full items-center justify-center rounded-md px-4 py-3.5 text-sm font-semibold transition ${
                    tier.highlight
                      ? "bg-[#2d8b81] text-white hover:bg-[#36a094]"
                      : "border border-white/[0.12] bg-white/5 text-white hover:bg-white/[0.08]"
                  }`}
                >
                  {tier.cta}
                </Link>
              </article>
            </Reveal>
          )
        })}
      </div>
    </section>
  )
}
