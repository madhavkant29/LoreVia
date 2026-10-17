import { describe, expect, it } from "vitest"

import type { BillingSubscription } from "@/lib/api/billing"
import type { User } from "@/types/user"

import { dailyGoalError, formatBillingDate, getBillingPresentation, usernameError } from "./settingsPage.helpers"

const user: User = {
  id: "user-1",
  email: "author@example.com",
  tier: "author",
  plan_tier: "author",
  tier_label: "Author",
  trial_active: false,
  reading_mode: "analyst",
  daily_word_goal: 1000,
  today_word_count: 250,
  login_streak_days: 3,
  longest_login_streak_days: 5,
  login_activity_dates: [],
  email_verified: true,
  messaging_permission: "friends_only",
  created_at: "2026-01-01T00:00:00Z",
}

describe("getBillingPresentation", () => {
  it("rejects invalid daily goals without silently coercing or rounding", () => {
    for (const value of ["", "0", "-1", "1.5", "word", "1000001", "1e3"]) expect(dailyGoalError(value)).toBeTruthy()
    for (const value of ["1", "1000000", " 2000 "]) expect(dailyGoalError(value)).toBeNull()
  })

  it("validates username characters and length while retaining Unicode letters", () => {
    for (const value of ["", "ab", "bad name", "bad@name", "a".repeat(33)]) expect(usernameError(value)).toBeTruthy()
    for (const value of ["a-name_2", " Léa ", "a".repeat(32)]) expect(usernameError(value)).toBeNull()
  })

  it("handles missing or malformed dates without crashing account settings", () => {
    expect(formatBillingDate("invalid")).toBeNull()
    expect(formatBillingDate("")).toBeNull()
    expect(formatBillingDate("2027-01-01T00:00:00Z")).toBe("January 1, 2027")
  })
  it("formats active annual billing details for the settings surface", () => {
    const subscription: BillingSubscription = {
      plan: "author_annual",
      plan_tier: "author",
      status: "active",
      display_state: "active",
      price: { amount: 120, currency: "USD", interval: "year" },
      current_period_start: "2026-01-01T00:00:00Z",
      current_period_end: "2027-01-01T00:00:00Z",
      cancel_at_period_end: false,
      cancellation_scheduled_at: null,
      next_charge_at: "2027-01-01T00:00:00Z",
      auto_renew: true,
      last_payment_status: "paid",
      has_paddle_subscription: true,
    }

    expect(getBillingPresentation(subscription, user)).toMatchObject({
      paidUser: true,
      displayTier: "Author",
      billingDisplayState: "active",
      billingPlanLabel: "Author",
      billingPriceLabel: "$120/year",
      nextRenewalLabel: "January 1, 2027",
      cancellationEndLabel: "January 1, 2027",
    })
  })

  it("returns safe free-account defaults without a subscription", () => {
    expect(getBillingPresentation(null, null)).toMatchObject({
      paidUser: false,
      billingDisplayState: "free",
      billingPriceLabel: null,
      nextRenewalLabel: null,
      cancellationEndLabel: null,
    })
  })
})
