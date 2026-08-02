export function scheduleIdleWork(callback: () => void, fallbackDelayMs: number) {
  if (typeof window.requestIdleCallback === "function") {
    const handle = window.requestIdleCallback(callback)
    return () => window.cancelIdleCallback(handle)
  }

  const handle = window.setTimeout(
    () => callback(),
    fallbackDelayMs,
  )
  return () => window.clearTimeout(handle)
}

export function scheduleTrackedTimeout(
  timeoutIds: Set<number>,
  callback: () => void,
  delay: number,
) {
  const id = window.setTimeout(() => {
    timeoutIds.delete(id)
    callback()
  }, delay)
  timeoutIds.add(id)
}
