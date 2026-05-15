import type { Metadata } from "next"

import { PricingPlans } from "@/components/billing/PricingPlans"
import { LegalPageShell } from "@/components/legal/LegalPageShell"

export const metadata: Metadata = {
  title: "Pricing",
  description: "Compare LoreVia for authors plans for manuscript drafting, continuity work, revision, and larger story worlds before creating an account.",
  alternates: {
    canonical: "/pricing",
  },
}

export default function PricingPage() {
  return (
    <LegalPageShell
      eyebrow="Pricing"
      title="Pricing for authors doing serious manuscript work"
      description="See exactly what is included for free, what happens after the 10-day trial, and which LoreVia plans are paid before you create an account."
      effectiveDate="May 8, 2026"
      notice="Every new signup gets 10 days of Author access with no credit card required, then falls back to Free unless you choose a paid plan."
      maxWidth="wide"
    >
      <PricingPlans surface="public" />
    </LegalPageShell>
  )
}
