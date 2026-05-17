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
      ? "Explore LoreVia with a single project."
      : tier.name === "Author"
        ? "For active manuscript drafting, revision, collaborator feedback, and continuity work."
        : "For multi-book projects and expansive story worlds.",
  bullets:
    tier.name === "Free"
      ? [
          "1 upload total",
          "Explore sample LoreVia workflows",
          "Join author-invited beta reads for free",
          "Basic story recall with strict limits",
          "Short chapter summaries only",
          "3 searches/day, 1 prediction/day, 1 advisor turn/day, 1 continuity check/day",
        ]
      : tier.name === "Author"
        ? [
            "Everything in Free, plus",
            "Continuity scans and manuscript feedback",
            "Author collaboration workflows",
            "Character reference generation",
            "Relationship and timeline tracking",
            "High monthly usage limits",
          ]
        : [
            "Everything in Author, plus",
            "Cross-book continuity analysis",
            "Advanced world consistency checks",
            "Series-wide relationship tracking",
            "Early access to new features",
            "Extended analysis capacity",
          ],
  cta:
    tier.name === "Free"
      ? "Start free"
      : tier.name === "Author"
        ? "Start writing"
        : "Build your world",
}))

export function HomePricingSection({ ctaHref }: HomePricingSectionProps) {
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")

  return (
    <section id="pricing" className="relative mx-auto max-w-7xl px-5 py-24 md:px-8 md:py-30">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="font-display text-4xl font-semibold leading-[1.02] text-white md:text-6xl">
          Choose the workspace that fits your writing.
        </h2>
        <p className="mt-5 text-base leading-8 text-slate-400 md:text-lg">
          Every signup starts with a 10-day Author trial at no charge. After that, Free remains available and only Author or Architect are paid.
        </p>
      </div>

      <div className="mt-8 flex justify-center">
        <div className="inline-flex items-center rounded-full border border-white/10 bg-[#0b1020] px-2 py-2 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.95)]">
          {(["monthly", "annual"] as const).map((cycle) => (
            <button
              key={cycle}
              type="button"
              onClick={() => setBillingCycle(cycle)}
              className={`rounded-full px-5 py-2.5 text-sm font-semibold transition ${
                billingCycle === cycle
                  ? "bg-cyan-300 text-slate-950"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              {cycle === "annual" ? "Yearly" : "Monthly"}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {marketingPricingContent.map((tier, index) => {
          const price = pricingTierPrice(tier, billingCycle)
          const suffix = pricingTierPriceSuffix(tier, billingCycle)
          const savings = billingCycle === "annual" ? pricingTierAnnualSavings(tier) : 0

          return (
            <Reveal key={tier.name} delay={index * 70} className="h-full">
              <article
                className={`relative flex h-full min-h-[42rem] flex-col rounded-2xl p-6 transition hover:-translate-y-1 md:p-8 ${
                  tier.highlight
                    ? "border border-cyan-300/50 bg-[#121b30] shadow-[0_24px_70px_-45px_rgba(125,211,252,0.8)]"
                    : "border border-white/10 bg-[#080d18]"
                }`}
              >
                {tier.highlight ? (
                  <div className="absolute -top-3 left-6 rounded-md bg-cyan-300 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-950">
                    Best value
                  </div>
                ) : null}

                <div className="flex min-h-[10.5rem] flex-col justify-start">
                  <h3 className="text-xl font-semibold text-white md:text-2xl">{tier.name}</h3>
                  <p className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                    {pricingTierAccessLabel(tier)}
                  </p>
                  <p className="mt-4 text-sm leading-7 text-slate-400">{tier.subtitle}</p>
                </div>

                <div className="mt-8 min-h-[5.5rem]">
                  <div className="flex items-end gap-2">
                    <span className="text-5xl font-semibold tracking-tight text-white">${price}</span>
                    {suffix ? <span className="pb-1 text-sm text-slate-500">{suffix}</span> : null}
                  </div>
                  {savings > 0 ? (
                    <p className="mt-3 text-sm font-medium text-cyan-100">Save ${savings} with yearly billing</p>
                  ) : (
                    <div className="mt-3 h-[1.5rem]" aria-hidden="true" />
                  )}
                </div>

                <ul className="mt-8 flex-1 space-y-4 text-sm leading-7 text-slate-300">
                  {tier.bullets.map((bullet) => (
                    <li key={bullet} className="flex items-start gap-3">
                      <span className={tier.highlight ? "pt-0.5 text-cyan-200" : "pt-0.5 text-slate-500"}>+</span>
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={ctaHref}
                  className={`mt-10 inline-flex w-full items-center justify-center rounded-md px-4 py-3.5 text-sm font-semibold transition ${
                    tier.highlight
                      ? "bg-white text-slate-950 hover:bg-slate-200"
                      : "border border-white/10 text-white hover:border-white/25 hover:bg-white/8"
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
