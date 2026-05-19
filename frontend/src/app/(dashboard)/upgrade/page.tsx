import type { Metadata } from "next"

import { PricingPlans } from "@/components/billing/PricingPlans"

export const metadata: Metadata = {
  title: "Upgrade",
}

export default function UpgradePage() {
  return (
    <section className="space-y-4">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted-foreground">Pricing</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-foreground">Choose the plan that matches your work</h1>
        <p className="mt-3 max-w-3xl text-base leading-7 text-muted-foreground">
          Free stays included with your account. Compare Free, Author, and Architect, switch billing cadence, and start checkout without leaving the app.
        </p>
      </div>

      <PricingPlans surface="app" />
    </section>
  )
}
