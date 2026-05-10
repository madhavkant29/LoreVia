const GOOGLE_TERMS_REQUIRED_DETAIL =
  "You must accept the Terms, Compliance notice, and EULA before creating an account with Google."

export function normalizeOAuthLoginError(error: string | null | undefined): string | null {
  const detail = (error || "").trim()
  if (!detail) {
    return null
  }

  if (detail === GOOGLE_TERMS_REQUIRED_DETAIL) {
    return "First-time Google users need to start from Create one so you can accept the Terms, Compliance notice, and EULA."
  }

  return detail
}

export function isGoogleSignupRedirectError(error: string | null | undefined): boolean {
  return normalizeOAuthLoginError(error)?.includes("First-time Google users") ?? false
}
