type CacheRecord = {
  value: unknown
  expiresAt: number
}

const responseCache = new Map<string, CacheRecord>()
const inFlightRequests = new Map<string, Promise<unknown>>()

export async function cachedGet<T>(
  key: string,
  ttlMs: number,
  fetcher: () => Promise<T>,
): Promise<T> {
  const now = Date.now()
  const cached = responseCache.get(key)
  if (cached && cached.expiresAt > now) {
    return cached.value as T
  }

  const pending = inFlightRequests.get(key)
  if (pending) {
    return pending as Promise<T>
  }

  const request = fetcher()
    .then((value) => {
      responseCache.set(key, { value, expiresAt: Date.now() + Math.max(0, ttlMs) })
      return value
    })
    .finally(() => {
      inFlightRequests.delete(key)
    })

  inFlightRequests.set(key, request as Promise<unknown>)
  return request
}

export function invalidateCachedGets(matcher: string | RegExp): void {
  for (const key of responseCache.keys()) {
    const shouldDelete = typeof matcher === "string" ? key.startsWith(matcher) : matcher.test(key)
    if (shouldDelete) {
      responseCache.delete(key)
    }
  }
}

export function clearCachedGets(): void {
  responseCache.clear()
  inFlightRequests.clear()
}
