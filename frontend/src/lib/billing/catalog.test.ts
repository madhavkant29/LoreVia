import { describe, expect, it } from "vitest"

import { pricingTierAccessLabel, pricingTierGuestCtaLabel, pricingTiers } from "./catalog"

describe("pricing catalog", () => {
  it("marks the free tier as included instead of paid", () => {
    const freeTier = pricingTiers.find((tier) => tier.name === "Free")

    expect(freeTier?.access).toBe("free")
    expect(pricingTierAccessLabel(freeTier!)).toBe("Included with every account")
    expect(pricingTierGuestCtaLabel(freeTier!)).toBe("Create free account")
  })

  it("marks checkout tiers as paid subscriptions", () => {
    const paidTiers = pricingTiers.filter((tier) => tier.access === "paid")

    expect(paidTiers.map((tier) => tier.name)).toEqual(["Author", "Architect"])
    expect(paidTiers.every((tier) => pricingTierAccessLabel(tier) === "Paid subscription")).toBe(true)
    expect(paidTiers.every((tier) => pricingTierGuestCtaLabel(tier) === "Create account for free trial")).toBe(true)
  })
})
