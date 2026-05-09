import type { UserTier } from "@/types/user"

export type PaidPlanCode =
  | "reader_monthly"
  | "reader_annual"
  | "author_monthly"
  | "author_annual"
  | "architect_monthly"
  | "architect_annual"

export function canUseAuthorFeatures(tier?: UserTier | null) {
  return tier === "author" || tier === "architect" || tier === "admin"
}

export function isPaidTier(tier?: UserTier | null) {
  return tier === "reader" || canUseAuthorFeatures(tier)
}

export function tierLabel(tier?: UserTier | null) {
  switch (tier) {
    case "reader":
      return "Reader"
    case "author":
      return "Author"
    case "architect":
      return "Lore Architect"
    case "admin":
      return "Admin"
    case "free":
    default:
      return "Free"
  }
}
