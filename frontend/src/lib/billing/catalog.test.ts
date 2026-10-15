import { describe, expect, it } from "vitest"

import {
  buildPricingOffersJsonLd,
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

  it("advertises the Architect plan's exact 60/day advisor and scan limits", () => {
    const architectTier = pricingTiers.find((tier) => tier.name === "Architect")
    const authorTier = pricingTiers.find((tier) => tier.name === "Author")

    expect(authorTier?.bullets).toContain("Up to 30 Story Advisor turns per day")
    expect(authorTier?.bullets).toContain("Up to 30 continuity and editorial scans per day; AI-intensive features share monthly capacity")
    expect(architectTier?.bullets).toContain("Up to 60 Story Advisor turns per day")
    expect(architectTier?.bullets).toContain("Up to 60 continuity and editorial scans per day; AI-intensive features share monthly capacity")
  })

  it("returns cadence-aware prices and suffixes", () => {
    const authorTier = pricingTiers.find((tier) => tier.name === "Author")
    const architectTier = pricingTiers.find((tier) => tier.name === "Architect")
    const freeTier = pricingTiers.find((tier) => tier.name === "Free")

    expect(pricingTierPrice(authorTier!, "monthly")).toBe(19)
    expect(pricingTierPrice(authorTier!, "annual")).toBe(190)
    expect(pricingTierPrice(architectTier!, "monthly")).toBe(39)
    expect(pricingTierPrice(architectTier!, "annual")).toBe(390)
    expect(pricingTierPriceSuffix(authorTier!, "monthly")).toBe("/mo")
    expect(pricingTierPriceSuffix(authorTier!, "annual")).toBe("/year")
    expect(pricingTierPriceSuffix(freeTier!, "annual")).toBe("")
  })

  it("calculates annual savings for paid tiers only", () => {
    const authorTier = pricingTiers.find((tier) => tier.name === "Author")
    const architectTier = pricingTiers.find((tier) => tier.name === "Architect")
    const freeTier = pricingTiers.find((tier) => tier.name === "Free")

    expect(pricingTierAnnualSavings(authorTier!)).toBe(38)
    expect(pricingTierAnnualSavings(architectTier!)).toBe(78)
    expect(pricingTierAnnualSavings(freeTier!)).toBe(0)
  })

  it("builds Free plus monthly and annual structured-data offers", () => {
    const offers = buildPricingOffersJsonLd("https://getlorevia.com/pricing")

    expect(offers).toHaveLength(5)
    expect(offers.map((offer) => ({
      name: offer.name,
      price: offer.price,
      sku: "sku" in offer ? offer.sku : null,
      billingDuration: "priceSpecification" in offer
        ? (offer.priceSpecification as { billingDuration: string }).billingDuration
        : null,
    }))).toEqual([
      { name: "Free", price: "0", sku: null, billingDuration: null },
      { name: "Author Monthly", price: "19", sku: "author_monthly", billingDuration: "P1M" },
      { name: "Author Annual", price: "190", sku: "author_annual", billingDuration: "P1Y" },
      { name: "Architect Monthly", price: "39", sku: "architect_monthly", billingDuration: "P1M" },
      { name: "Architect Annual", price: "390", sku: "architect_annual", billingDuration: "P1Y" },
    ])
    expect(offers.every((offer) => offer.priceCurrency === "USD")).toBe(true)
    expect(offers.every((offer) => offer.url === "https://getlorevia.com/pricing")).toBe(true)
  })
})
