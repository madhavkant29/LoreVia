const PADDLE_TEST_TOKEN_PREFIX = "test_"
const PADDLE_LIVE_TOKEN_PREFIX = "live_"
const PADDLE_TRANSACTION_QUERY_KEY = "_ptxn"
const BILLING_CONFIRMATION_QUERY_KEY = "lvct"
export const PADDLE_SCRIPT_SRC = "https://cdn.paddle.com/paddle/v2/paddle.js"

export type PaddleEnvironment = "sandbox" | "production"

export function getPaddleClientToken(): string | null {
  const token = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN?.trim()
  return token ? token : null
}

export function getPaddleEnvironment(token: string | null): PaddleEnvironment | null {
  if (!token) return null
  if (token.startsWith(PADDLE_TEST_TOKEN_PREFIX)) return "sandbox"
  if (token.startsWith(PADDLE_LIVE_TOKEN_PREFIX)) return "production"
  return null
}

export function getPaddleTransactionId(
  searchParams: Pick<URLSearchParams, "get"> | null | undefined
): string | null {
  const transactionId = searchParams?.get(PADDLE_TRANSACTION_QUERY_KEY)?.trim()
  return transactionId ? transactionId : null
}

export function getTransactionIdFromCheckoutUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    return getPaddleTransactionId(new URL(url).searchParams)
  } catch {
    return null
  }
}

export function getBillingConfirmationToken(
  searchParams: Pick<URLSearchParams, "get"> | null | undefined
): string | null {
  const token = searchParams?.get(BILLING_CONFIRMATION_QUERY_KEY)?.trim()
  return token ? token : null
}

export function getBillingConfirmationTokenFromCheckoutUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    return getBillingConfirmationToken(new URL(url).searchParams)
  } catch {
    return null
  }
}

export function buildPaddleCheckoutSettings(successUrl?: string) {
  const locale =
    typeof navigator !== "undefined" && navigator.language
      ? navigator.language
      : "en"

  return {
    allowLogout: false as const,
    displayMode: "overlay" as const,
    locale,
    theme: "light" as const,
    variant: "one-page" as const,
    ...(successUrl ? { successUrl } : {}),
  }
}
