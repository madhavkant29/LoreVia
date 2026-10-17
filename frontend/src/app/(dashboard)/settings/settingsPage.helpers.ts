import type { BillingSubscription } from "@/lib/api/billing"
import { tierLabel } from "@/lib/billing/plans"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { toolsForPlacement } from "@/lib/workspace/toolRegistry"
import type { User } from "@/types/user"

export const DELETION_REQUEST_EMAIL = "support@mail.getlorevia.com"
export const DASHBOARD_VISIBILITY_TOOLS = toolsForPlacement("dashboard").filter((tool) => !tool.nonHideable)

export function formatBillingDate(value: string) {
  if (!Number.isFinite(new Date(value).getTime())) return null
  return new Intl.DateTimeFormat("en-US", { dateStyle: "long", timeZone: "UTC" }).format(new Date(value))
}

export function dailyGoalError(value: string) {
  const goal = Number(value)
  return /^\d+$/.test(value.trim()) && Number.isSafeInteger(goal) && goal >= 1 && goal <= 1000000 ? null : "Enter a whole number from 1 to 1,000,000 words."
}

export function usernameError(value: string) {
  const name = value.trim()
  return Array.from(name).length >= 3 && Array.from(name).length <= 32 && /^[\p{L}\p{N}_-]+$/u.test(name) ? null : "Use 3–32 letters, numbers, hyphens, or underscores."
}

export function getBillingPresentation(billingStatus: BillingSubscription | null, user: User | null) {
  const paidUser = Boolean(user && user.tier !== "free" && !user.trial_active)

  return {
    paidUser,
    displayTier: user?.tier_label ?? tierLabel(user?.tier),
    billingDisplayState: billingStatus?.display_state ?? (user?.trial_active ? "trial" : paidUser ? "active" : "free"),
    billingPlanLabel: tierLabel(billingStatus?.plan_tier ?? user?.plan_tier),
    billingPriceLabel: billingStatus
      ? `$${billingStatus.price.amount}${billingStatus.price.interval === "year" ? "/year" : "/month"}`
      : null,
    nextRenewalLabel: billingStatus?.next_charge_at ? formatBillingDate(billingStatus.next_charge_at) : null,
    cancellationEndLabel: billingStatus?.current_period_end ? formatBillingDate(billingStatus.current_period_end) : null,
    refundRequestHref: `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("LoreVia refund request")}`,
  }
}
