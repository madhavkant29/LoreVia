import type { PaidPlanCode } from "@/lib/billing/plans"
import pricingCatalog from "./pricing-catalog.json"

export type BillingCycle = "monthly" | "annual"

export type PricingTierAccess = "free" | "paid"

export type PricingTier = {
  key: string
  name: string
  badge: string
  access: PricingTierAccess
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

export function pricingTierAccessLabel(tier: PricingTier) {
  return tier.access === "free" ? "Included with every account" : "Paid subscription"
}

export function pricingTierGuestCtaLabel(tier: PricingTier) {
  return tier.access === "free" ? "Create free account" : "Create account for free trial"
}

export function pricingTierPrice(tier: PricingTier, billingCycle: BillingCycle) {
  return billingCycle === "annual" ? tier.priceAnnual : tier.priceMonthly
}

export function pricingTierPriceSuffix(tier: PricingTier, billingCycle: BillingCycle) {
  if (tier.access === "free") return ""
  return billingCycle === "annual" ? "/yr" : "/mo"
}

export function pricingTierAnnualSavings(tier: PricingTier) {
  if (tier.access === "free") return 0
  return Math.max(tier.priceMonthly * 12 - tier.priceAnnual, 0)
}

export const pricingTiers: PricingTier[] = pricingCatalog.tiers.map((tier) => ({
  key: tier.key,
  name: tier.name,
  badge: tier.badge,
  access: tier.access as PricingTierAccess,
  subtitle: tier.subtitle,
  highlight: tier.highlight,
  cta: tier.cta,
  bullets: tier.bullets,
  monthlyCode: tier.monthly_code as PaidPlanCode | null,
  annualCode: tier.annual_code as PaidPlanCode | null,
  message: tier.message ?? null,
  priceMonthly: tier.price_monthly,
  priceAnnual: tier.price_annual,
}))
