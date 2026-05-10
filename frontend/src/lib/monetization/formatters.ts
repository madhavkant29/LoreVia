import type { PointLedgerEntry } from "@/types/monetization"

export function formatPointsDelta(pointsDelta: number): string {
  if (pointsDelta > 0) {
    return `+${pointsDelta}`
  }
  return String(pointsDelta)
}

export function formatPointEntryLabel(entry: PointLedgerEntry): string {
  if (entry.entry_type === "grant" && entry.source_type === "referral_reward") {
    return "Referral reward"
  }
  if (entry.entry_type === "grant" && entry.source_type === "first_processed_book") {
    return "First processed book"
  }
  if (entry.entry_type === "spend" && entry.source_type === "overflow_search") {
    return "Search overflow"
  }
  if (entry.entry_type === "spend" && entry.source_type === "overflow_prediction") {
    return "Prediction overflow"
  }
  if (entry.entry_type === "spend" && entry.source_type === "overflow_high_cost_authoring") {
    return "Advisor overflow"
  }
  if (entry.entry_type === "expire") {
    return "Expired points"
  }
  return "Points activity"
}
