export const UNKNOWN_RELEASE_SHA = "unknown"

const RELEASE_SHA_PATTERN = /^[0-9a-f]{7,64}$/
type ReleaseEnvironment = Record<string, string | undefined>

export function normalizeReleaseSha(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim().toLowerCase()
  return RELEASE_SHA_PATTERN.test(normalized) ? normalized : UNKNOWN_RELEASE_SHA
}

export function currentFrontendReleaseSha(
  environment: ReleaseEnvironment = process.env,
): string {
  return normalizeReleaseSha(environment.VERCEL_GIT_COMMIT_SHA || environment.RELEASE_SHA)
}
