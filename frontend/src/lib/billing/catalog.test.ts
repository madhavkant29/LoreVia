import { describe, expect, it } from "vitest"

import {
  pricingTierAccessLabel,
  pricingTierAnnualSavings,
  pricingTierGuestCtaLabel,
  pricingTierPrice,
  pricingTierPriceSuffix,
  pricingTiers,
} from "./catalog"

describe("pricing catalog", () => {
  it("marks the free tier as included instead of paid", () => {
    const freeTier = pricingTiers.find((tier) => tier.name === "Free")

    expect(freeTier?.access).toBe("free")
    expect(pricingTierAccessLabel(freeTier!)).toBe("Included with every account")
    expect(pricingTierGuestCtaLabel(freeTier!)).toBe("Create free account")
    expect(freeTier?.bullets).toEqual([
      "Read existing projects",
      "Export manuscript and novel files",
      "1 Story Advisor turn per week",
      "Join invited beta reads",
      "Author tools only during the 10-day trial",
    ])
  })

  it("marks checkout tiers as paid subscriptions", () => {
    const paidTiers = pricingTiers.filter((tier) => tier.access === "paid")

    expect(paidTiers.map((tier) => tier.name)).toEqual(["Author", "Architect"])
    expect(paidTiers.every((tier) => pricingTierAccessLabel(tier) === "Paid subscription")).toBe(true)
    expect(paidTiers.every((tier) => pricingTierGuestCtaLabel(tier) === "Create account for free trial")).toBe(true)
  })

  it("returns cadence-aware prices and suffixes", () => {
    const authorTier = pricingTiers.find((tier) => tier.name === "Author")
    const freeTier = pricingTiers.find((tier) => tier.name === "Free")

    expect(pricingTierPrice(authorTier!, "monthly")).toBe(29)
    expect(pricingTierPrice(authorTier!, "annual")).toBe(249)
    expect(pricingTierPriceSuffix(authorTier!, "monthly")).toBe("/mo")
    expect(pricingTierPriceSuffix(authorTier!, "annual")).toBe("/year")
    expect(pricingTierPriceSuffix(freeTier!, "annual")).toBe("")
  })

  it("calculates annual savings for paid tiers only", () => {
    const authorTier = pricingTiers.find((tier) => tier.name === "Author")
    const architectTier = pricingTiers.find((tier) => tier.name === "Architect")
    const freeTier = pricingTiers.find((tier) => tier.name === "Free")

    expect(pricingTierAnnualSavings(authorTier!)).toBe(99)
    expect(pricingTierAnnualSavings(architectTier!)).toBe(139)
    expect(pricingTierAnnualSavings(freeTier!)).toBe(0)
  })
})
