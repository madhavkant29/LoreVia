import { afterEach, describe, expect, it, vi } from "vitest"

import {
  assertPaddleEnvironment,
  buildPaddleCheckoutSettings,
  getBillingConfirmationToken,
  getBillingConfirmationTokenFromCheckoutUrl,
  getAbsoluteCheckoutSuccessUrl,
  getPaddleClientToken,
  getPaddleEnvironment,
  getPublicAppUrl,
  getPaddleTransactionId,
  getTransactionIdFromCheckoutUrl,
} from "./paddle"

describe("paddle billing helpers", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it("returns the configured client-side token", () => {
    vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "live_example_token")

    expect(getPaddleClientToken()).toBe("live_example_token")
  })

  it("returns null for a blank client-side token", () => {
    vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "   ")

    expect(getPaddleClientToken()).toBeNull()
  })

  it("detects sandbox tokens from the test prefix", () => {
    expect(getPaddleEnvironment("test_abcdefghijklmnopqrstuvwxyz1")).toBe("sandbox")
  })

  it("detects production tokens from the live prefix", () => {
    expect(getPaddleEnvironment("live_abcdefghijklmnopqrstuvwxyz1")).toBe("production")
  })

  it("returns null for unknown token formats", () => {
    expect(getPaddleEnvironment("pdl_invalid")).toBeNull()
  })

  it("throws for an invalid token in the strict environment helper", () => {
    expect(() => assertPaddleEnvironment("pdl_invalid")).toThrow(
      "Invalid Paddle client-side token. Expected a token starting with test_ or live_."
    )
  })

  it("extracts the transaction id from the Paddle query string", () => {
    const params = new URLSearchParams("_ptxn=txn_123")

    expect(getPaddleTransactionId(params)).toBe("txn_123")
  })

  it("returns null when the Paddle transaction id is missing", () => {
    const params = new URLSearchParams("plan=author_monthly")

    expect(getPaddleTransactionId(params)).toBeNull()
  })

  it("extracts the billing confirmation token from the checkout query string", () => {
    const params = new URLSearchParams("lvct=token_123")

    expect(getBillingConfirmationToken(params)).toBe("token_123")
  })

  it("extracts the Paddle transaction id from a checkout url", () => {
    expect(getTransactionIdFromCheckoutUrl("https://getlorevia.com/checkout?_ptxn=txn_456")).toBe("txn_456")
  })

  it("extracts the billing confirmation token from a checkout url", () => {
    expect(getBillingConfirmationTokenFromCheckoutUrl("https://getlorevia.com/checkout?_ptxn=txn_456&lvct=token_456")).toBe("token_456")
  })

  it("returns the normalized public app url", () => {
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://getlorevia.com/")

    expect(getPublicAppUrl()).toBe("https://getlorevia.com")
  })

  it("builds an absolute checkout success url from NEXT_PUBLIC_APP_URL", () => {
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://getlorevia.com/")

    expect(getAbsoluteCheckoutSuccessUrl()).toBe("https://getlorevia.com/checkout/success")
  })

  it("builds one-page overlay checkout settings with a success url", () => {
    const settings = buildPaddleCheckoutSettings("https://getlorevia.com/checkout/success")

    expect(settings.displayMode).toBe("overlay")
    expect(settings.variant).toBe("one-page")
    expect(settings.allowLogout).toBe(false)
    expect(settings.successUrl).toBe("https://getlorevia.com/checkout/success")
  })

  it("defaults the checkout success url to the public app url", () => {
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://getlorevia.com")

    const settings = buildPaddleCheckoutSettings()

    expect(settings.successUrl).toBe("https://getlorevia.com/checkout/success")
  })
})
