import type { Metadata } from "next"
import { headers } from "next/headers"

import { PricingPageIntro, PricingPlans } from "@/components/billing/PricingPlans"

export const metadata: Metadata = {
  title: "Upgrade",
}

export default async function UpgradePage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined

  return (
    <section>
      <PricingPageIntro />
      <div className="mt-8">
        <PricingPlans surface="app" nonce={nonce} />
      </div>
    </section>
  )
}
