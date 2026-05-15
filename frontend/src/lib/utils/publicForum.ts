export function formatReputationScore(score: number): string {
  const value = Number.isFinite(score) ? Math.trunc(score) : 0
  return value > 0 ? `+${value}` : String(value)
}

export function formatWordProgress(words: number): string {
  const value = Math.max(0, Math.trunc(words || 0))
  if (value >= 1000) {
    const compact = value / 1000
    return `${Number.isInteger(compact) ? compact.toFixed(0) : compact.toFixed(1)}k words`
  }
  return `${value} words`
}
