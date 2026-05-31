import { describe, expect, it } from "vitest"

import { normalizeLoginError, shouldShowCreateAccountCta } from "./loginMessages"

describe("loginMessages", () => {
  it("maps the google terms requirement into a clearer login message", () => {
    expect(
      normalizeLoginError(
        "You must accept the Terms, Compliance notice, and EULA before creating an account with Google.",
      ),
    ).toBe(
      "First-time Google users need to start from Create one so you can accept the Terms, Compliance notice, and EULA.",
    )
  })

  it("maps unauthorized email sign-in errors to create-account guidance", () => {
    expect(normalizeLoginError(null, 401)).toBe(
      "No account found for that sign-in. Create one if you're new to LoreVia, or use the same sign-in method you originally chose, like Google.",
    )
  })

  it("maps invalid credentials details to an invalid-password message", () => {
    expect(normalizeLoginError("Invalid credentials")).toBe(
      "Invalid email or password.",
    )
  })

  it("maps cloudflare origin errors to a retryable sign-in message", () => {
    expect(
      normalizeLoginError(
        "The origin web server returned an invalid or incomplete response to Cloudflare.",
      ),
    ).toBe("Sign-in was temporarily unavailable. Please try again.")
  })

  it("maps server failures without details to a retryable sign-in message", () => {
    expect(normalizeLoginError(null, 502)).toBe("Sign-in was temporarily unavailable. Please try again.")
  })

  it("passes through unrelated auth errors", () => {
    expect(normalizeLoginError("OAuth sign-in failed.")).toBe("OAuth sign-in failed.")
  })

  it("shows the create-account cta for first-time google users", () => {
    expect(
      shouldShowCreateAccountCta(
        "First-time Google users need to start from Create one so you can accept the Terms, Compliance notice, and EULA.",
      ),
    ).toBe(true)
  })

  it("shows the create-account cta for missing-account guidance", () => {
    expect(
      shouldShowCreateAccountCta(
        "No account found for that sign-in. Create one if you're new to LoreVia, or use the same sign-in method you originally chose, like Google.",
      ),
    ).toBe(true)
  })
})
