import type { PaidPlanCode } from "@/lib/billing/plans"

export type BillingCycle = "monthly" | "annual"

export type PricingTier = {
  name: string
  badge: string
  subtitle: string
  highlight: boolean
  cta: string
  bullets: string[]
  monthlyCode: PaidPlanCode | null
  annualCode: PaidPlanCode | null
  message?: string | null
  priceMonthly: number
  priceAnnual: number
}

export const pricingTiers: PricingTier[] = [
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
    priceMonthly: 29,
    priceAnnual: 290,
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
    priceMonthly: 49,
    priceAnnual: 490,
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
