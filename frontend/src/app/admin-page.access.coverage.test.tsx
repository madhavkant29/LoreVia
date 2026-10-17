// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  AdminPage,
  adminApiMock,
  clickButton,
  cleanupAdminPage,
  flush,
  getContainer,
  ownerSession,
  renderPage,
  setFieldValue,
  waitForText,
} from "./admin-page.test-utils"

describe("AdminPage access handling", () => {
  it("opens the first permitted area for a scoped moderator", async () => {
    adminApiMock.session.mockResolvedValueOnce({
      ...ownerSession,
      is_owner: false,
      scopes: ["moderation_admin"],
    })

    await renderPage(<AdminPage />)
    await waitForText("Gate Draft")

    expect(getContainer().querySelector('button[aria-current="page"]')?.textContent).toContain("Moderation")
    expect(adminApiMock.publicShares).toHaveBeenCalledTimes(1)
    expect(adminApiMock.reports).toHaveBeenCalledTimes(1)
    expect(adminApiMock.metrics).not.toHaveBeenCalled()
    expect(adminApiMock.billingStatus).not.toHaveBeenCalled()
  })

  it("handles step-up verification and missing admin access", async () => {
    adminApiMock.session
      .mockResolvedValueOnce({ ...ownerSession, requires_step_up: true })
      .mockResolvedValueOnce(ownerSession)
    await renderPage(<AdminPage />)
    await waitForText("Verify password")

    setFieldValue(getContainer().querySelector("input[type='password']") as HTMLInputElement, "secret")
    await act(async () => {
      clickButton("Verify")
      await flush()
    })
    expect(adminApiMock.stepUp).toHaveBeenCalledWith("secret")

    cleanupAdminPage()
    adminApiMock.session.mockRejectedValueOnce(new Error("not found"))
    await renderPage(<AdminPage />)
    await waitForText("404")
    expect(getContainer().textContent).toContain("Not found.")
  })
})
