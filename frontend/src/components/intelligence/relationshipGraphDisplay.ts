export function graphStorageKey(bookId: string, chapter: number) {
  return `lorevia:graph-layout:${bookId}:${chapter}`
}

export function graphLabelKey(bookId: string) {
  return `lorevia:graph-labels:${bookId}`
}

export function relationshipLabel(value: string | null | undefined) {
  return (value || "connection").replaceAll("_", " ")
}

export function sentimentLabel(value: unknown) {
  if (typeof value !== "number" || Number.isNaN(value)) return null
  if (value >= 0.45) return "Strongly positive"
  if (value >= 0.15) return "Positive"
  if (value <= -0.45) return "Strongly tense"
  if (value <= -0.15) return "Tense"
  return "Mixed or neutral"
}

export function zoomPercentLabel(value: number) {
  return `${Math.round(value * 100)}%`
}

export function nodeInitial(name: string) {
  const trimmed = name.trim()
  return trimmed ? trimmed.charAt(0).toUpperCase() : "?"
}
