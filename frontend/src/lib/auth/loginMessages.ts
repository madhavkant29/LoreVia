const GOOGLE_TERMS_REQUIRED_DETAIL =
  "You must accept the Terms, Compliance notice, and EULA before creating an account with Google."

const MISSING_ACCOUNT_OR_METHOD_MESSAGE =
  "No account found for that sign-in. Create one if you're new to LoreVia, or use the same sign-in method you originally chose, like Google."

export function normalizeLoginError(error: string | null | undefined, status?: number): string | null {
  const detail = (error || "").trim()

  if (status === 401) {
    return MISSING_ACCOUNT_OR_METHOD_MESSAGE
  }

  if (!detail) {
    return null
  }

  if (detail === GOOGLE_TERMS_REQUIRED_DETAIL) {
    return "First-time Google users need to start from Create one so you can accept the Terms, Compliance notice, and EULA."
  }

  if (detail === "Invalid credentials" || detail === "User not found") {
    return MISSING_ACCOUNT_OR_METHOD_MESSAGE
  }

  return detail
}

export function shouldShowCreateAccountCta(error: string | null | undefined): boolean {
  const normalized = normalizeLoginError(error)
  if (!normalized) {
    return false
  }

  return (
    normalized.includes("First-time Google users") ||
    normalized.includes("No account found for that sign-in")
  )
}
