const PADDLE_TEST_TOKEN_PREFIX = "test_"
const PADDLE_LIVE_TOKEN_PREFIX = "live_"
const PADDLE_TRANSACTION_QUERY_KEY = "_ptxn"
const BILLING_CONFIRMATION_QUERY_KEY = "lvct"
export const PADDLE_SCRIPT_SRC = "https://cdn.paddle.com/paddle/v2/paddle.js"

export type PaddleCheckoutEvent = {
  data?: {
    transaction_id?: string
  }
  name?: string
}

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

export function assertPaddleEnvironment(token: string | null): PaddleEnvironment {
  const environment = getPaddleEnvironment(token)
  if (!environment) {
    throw new Error("Invalid Paddle client-side token. Expected a token starting with test_ or live_.")
  }
  return environment
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

export function shouldAbandonClosedCheckout(
  transactionId: string | null,
  completedTransactionId: string | null,
): transactionId is string {
  return Boolean(transactionId) && transactionId !== completedTransactionId
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

export function getPublicAppUrl(): string | null {
  const url = process.env.NEXT_PUBLIC_APP_URL?.trim()
  if (!url) return null

  try {
    return new URL(url).toString().replace(/\/$/, "")
  } catch {
    return null
  }
}

export function getAbsoluteCheckoutSuccessUrl(): string | null {
  const appUrl = getPublicAppUrl()
  if (!appUrl) return null
  return `${appUrl}/checkout/success`
}

export function buildPaddleCheckoutSettings(successUrl?: string) {
  const locale =
    typeof navigator !== "undefined" && navigator.language
      ? navigator.language
      : "en"
  const resolvedSuccessUrl = successUrl ?? getAbsoluteCheckoutSuccessUrl() ?? undefined

  return {
    allowLogout: false as const,
    displayMode: "overlay" as const,
    locale,
    showAddDiscounts: false,
    showAddTaxId: false,
    theme: "light" as const,
    variant: "one-page" as const,
    ...(resolvedSuccessUrl ? { successUrl: resolvedSuccessUrl } : {}),
  }
}
