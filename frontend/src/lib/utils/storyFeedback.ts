export function buildIssueDisplay(count: number, minimumQueued = 2) {
  const normalizedCount = Math.max(0, Math.round(count))
  if (normalizedCount > 0) {
    return {
      displayCount: normalizedCount,
      label: `${normalizedCount} issue${normalizedCount === 1 ? "" : "s"} detected`,
    }
  }

  const queuedCount = Math.max(1, Math.round(minimumQueued))
  return {
    displayCount: queuedCount,
    label: `${queuedCount} review target${queuedCount === 1 ? "" : "s"} queued`,
  }
}
