const GOOGLE_TERMS_REQUIRED_DETAIL =
  "You must accept the Terms, Compliance notice, and EULA before creating an account with Google."

const MISSING_ACCOUNT_OR_METHOD_MESSAGE =
  "No account found for that sign-in. Create one if you're new to LoreVia, or use the same sign-in method you originally chose, like Google."
const INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."
const TEMPORARY_SIGN_IN_MESSAGE = "Sign-in was temporarily unavailable. Please try again."

function isTemporaryOriginError(detail: string): boolean {
  const normalized = detail.toLowerCase()
  return (
    normalized.includes("origin web server returned an invalid or incomplete response") ||
    normalized.includes("origin_bad_gateway") ||
    normalized.includes("bad gateway") ||
    normalized.includes("cloudflare") ||
    normalized.includes("status code 500") ||
    normalized.includes("internal server error")
  )
}

export function normalizeLoginError(error: string | null | undefined, status?: number): string | null {
  const detail = (error || "").trim()

  if (!detail) {
    if (status === 401) return MISSING_ACCOUNT_OR_METHOD_MESSAGE
    if (status && status >= 500) return TEMPORARY_SIGN_IN_MESSAGE
    return null
  }

  if (isTemporaryOriginError(detail) || (status && status >= 500)) {
    return TEMPORARY_SIGN_IN_MESSAGE
  }

  if (detail === GOOGLE_TERMS_REQUIRED_DETAIL) {
    return "First-time Google users need to start from Create one so you can accept the Terms, Compliance notice, and EULA."
  }

  if (detail === "Invalid credentials") {
    return INVALID_CREDENTIALS_MESSAGE
  }

  if (detail === "User not found") {
    return MISSING_ACCOUNT_OR_METHOD_MESSAGE
  }

  if (status === 401) {
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
