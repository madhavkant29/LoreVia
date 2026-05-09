import type { Metadata } from "next"

import { PricingPlans } from "@/components/billing/PricingPlans"
import { LegalPageShell } from "@/components/legal/LegalPageShell"

export const metadata: Metadata = {
  title: "Pricing",
  description: "Explore LoreVia plans for readers, authors, and larger story worlds before creating an account.",
  alternates: {
    canonical: "/pricing",
  },
}

export default function PricingPage() {
  return (
    <LegalPageShell
      eyebrow="Pricing"
      title="Pricing for serious manuscript work"
      description="See the plans, compare annual and monthly billing, and decide whether LoreVia fits your reading or writing workflow before you create an account."
      effectiveDate="May 8, 2026"
      notice="Every new signup gets 10 days of Author access with no credit card required."
      maxWidth="wide"
    >
      <PricingPlans surface="public" />
    </LegalPageShell>
  )
}
