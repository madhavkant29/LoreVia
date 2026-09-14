import type { Metadata } from "next"
import { headers } from "next/headers"

import { PricingPlans } from "@/components/billing/PricingPlans"

export const metadata: Metadata = {
  title: "Upgrade",
}

export default async function UpgradePage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined

  return (
    <section className="space-y-4">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-stone-600 dark:text-slate-300">Pricing</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-foreground">Choose the plan that matches your work</h1>
      </div>

      <PricingPlans surface="app" nonce={nonce} />
    </section>
  )
}
