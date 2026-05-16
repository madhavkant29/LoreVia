import type { Metadata } from "next"

import { PricingPlans } from "@/components/billing/PricingPlans"
import { LegalPageShell } from "@/components/legal/LegalPageShell"

export const metadata: Metadata = {
  title: "Pricing",
  description: "Compare LoreVia plans for fiction authors doing manuscript intelligence, revision, continuity work, and invited beta-reader collaboration.",
  alternates: {
    canonical: "/pricing",
  },
}

export default function PricingPage() {
  return (
    <LegalPageShell
      eyebrow="Pricing"
      title="Pricing for fiction authors doing serious manuscript work"
      description="See exactly what is included in Free, what happens after the 10-day Author trial, and how Author and Architect compare before you create an account."
      effectiveDate="May 8, 2026"
      notice="Every new signup gets 10 days of Author access with no credit card required, then falls back to Free unless you choose a paid plan."
      maxWidth="wide"
    >
      <PricingPlans surface="public" />
    </LegalPageShell>
  )
}
