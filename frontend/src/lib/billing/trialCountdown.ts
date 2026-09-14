export type TrialCountdown = {
  expired: boolean
  label: string
}

export function getTrialCountdown(trialEndsAt: string | null | undefined, nowMs = Date.now()): TrialCountdown | null {
  if (!trialEndsAt) return null
  const endMs = new Date(trialEndsAt).getTime()
  if (!Number.isFinite(endMs)) return null

  const remainingMs = endMs - nowMs
  if (remainingMs <= 0) return { expired: true, label: "Trial ended" }

  const totalMinutes = Math.max(Math.ceil(remainingMs / 60_000), 1)
  const days = Math.floor(totalMinutes / (24 * 60))
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60)
  const minutes = totalMinutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days} ${days === 1 ? "day" : "days"}`)
  if (hours > 0) parts.push(`${hours} ${hours === 1 ? "hour" : "hours"}`)
  if (days === 0 && minutes > 0) parts.push(`${minutes} ${minutes === 1 ? "minute" : "minutes"}`)
  return { expired: false, label: `${parts.join(", ")} remaining` }
}
