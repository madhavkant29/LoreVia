import { describe, expect, it } from "vitest"

import { isGoogleSignupRedirectError, normalizeOAuthLoginError } from "./oauthMessages"

describe("oauthMessages", () => {
  it("maps the google terms requirement into a clearer login message", () => {
    expect(
      normalizeOAuthLoginError(
        "You must accept the Terms, Compliance notice, and EULA before creating an account with Google.",
      ),
    ).toBe(
      "First-time Google users need to start from Create one so you can accept the Terms, Compliance notice, and EULA.",
    )
  })

  it("passes through unrelated oauth errors", () => {
    expect(normalizeOAuthLoginError("OAuth sign-in failed.")).toBe("OAuth sign-in failed.")
  })

  it("detects the create-account redirect case", () => {
    expect(
      isGoogleSignupRedirectError(
        "You must accept the Terms, Compliance notice, and EULA before creating an account with Google.",
      ),
    ).toBe(true)
  })
})
