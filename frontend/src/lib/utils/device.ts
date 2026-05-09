const STORAGE_KEY = "lorevia-device-id"

function buildDeviceId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `lv-${crypto.randomUUID()}`
  }
  return `lv-${Math.random().toString(36).slice(2)}-${Date.now()}`
}

export function getOrCreateDeviceId() {
  if (typeof window === "undefined") {
    return "lv-server-fallback-0000"
  }

  const existing = window.localStorage.getItem(STORAGE_KEY)
  if (existing) {
    return existing
  }

  const created = buildDeviceId()
  window.localStorage.setItem(STORAGE_KEY, created)
  return created
}
