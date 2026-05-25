import type { UserTier } from "@/types/user"

export type PaidPlanCode =
  | "author_monthly"
  | "author_annual"
  | "architect_monthly"
  | "architect_annual"

export function canUseAuthorFeatures(tier?: UserTier | null) {
  return tier === "author" || tier === "architect"
}

export function isPaidTier(tier?: UserTier | null) {
  return canUseAuthorFeatures(tier)
}

export function tierLabel(tier?: UserTier | null) {
  switch (tier) {
    case "collaborator":
    case "reader":
      return "Invited beta reader"
    case "author":
      return "Author"
    case "architect":
      return "Architect"
    case "free":
    default:
      return "Free"
  }
}
