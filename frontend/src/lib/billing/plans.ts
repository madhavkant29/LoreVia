import type { User, UserTier } from "@/types/user"

export type PaidPlanCode =
  | "author_monthly"
  | "author_annual"
  | "architect_monthly"
  | "architect_annual"

const LEGACY_USER_TIER_ALIASES: Record<string, UserTier> = {
  collaborator: "free",
  reader: "free",
  pro: "author",
  power: "architect",
}

export function normalizeUserTier(tier?: string | null): UserTier {
  const cleaned = (tier || "free").trim().toLowerCase()
  if (cleaned === "author" || cleaned === "architect" || cleaned === "free") return cleaned
  return LEGACY_USER_TIER_ALIASES[cleaned] ?? "free"
}

export function normalizeUser(user: User): User {
  const hasTier = Object.prototype.hasOwnProperty.call(user, "tier")
  const hasPlanTier = Object.prototype.hasOwnProperty.call(user, "plan_tier")
  const tier = normalizeUserTier(hasTier ? user.tier : null)
  const planTier = normalizeUserTier(hasPlanTier ? user.plan_tier : tier)
  return {
    ...user,
    ...(hasTier ? { tier } : {}),
    ...(hasPlanTier ? { plan_tier: planTier } : {}),
    ...(!user.tier_label && hasTier ? { tier_label: tierLabel(tier) } : {}),
  }
}

export function canUseAuthorFeatures(tier?: string | null) {
  const normalized = normalizeUserTier(tier)
  return normalized === "author" || normalized === "architect"
}

export function isPaidTier(tier?: string | null) {
  return canUseAuthorFeatures(tier)
}

export function tierLabel(tier?: string | null) {
  switch (normalizeUserTier(tier)) {
    case "author":
      return "Author"
    case "architect":
      return "Architect"
    case "free":
    default:
      return "Free"
  }
}
