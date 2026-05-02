export const API_BASE = "/api/v1"

export function resolveApiOrigin() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL
  if (apiUrl) {
    try {
      return new URL(apiUrl).origin
    } catch {
      // Fall through to browser or local defaults.
    }
  }

  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin
  }

  return "http://localhost:8000"
}

export const CONFIDENCE_THRESHOLDS = {
  SHOW_IN_UI: 0.45,
  CONFIRMED: 0.70,
  SUBJECTIVE_CAP: 0.50,
}

export const TRAIT_TYPE_LABELS: Record<string, string> = {
  objective: "Confirmed",
  subjective: "Described",
  abstract: "Implied",
}

export const RELATIONSHIP_COLORS: Record<string, string> = {
  ally: "#16a34a",
  enemy: "#dc2626",
  romantic: "#db2777",
  family: "#7c3aed",
  political: "#d97706",
  mentor: "#0891b2",
  rival: "#ea580c",
  neutral: "#6b7280",
}

export const STATUS_COLORS: Record<string, string> = {
  introduced: "bg-blue-100 text-blue-700",
  ongoing: "bg-amber-100 text-amber-700",
  resolved: "bg-green-100 text-green-700",
  abandoned: "bg-gray-100 text-gray-500",
  unknown: "bg-purple-100 text-purple-700",
}

export const SUMMARY_MODE_LABELS: Record<string, string> = {
  short: "Quick recap",
  detailed: "Full analysis",
  key_points: "Key points",
}
