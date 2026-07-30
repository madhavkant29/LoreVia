// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  AdminPage,
  adminApiMock,
  clickButton,
  renderPage,
  sectionByHeading,
  setFieldValue,
  flush,
  waitForText,
  getContainer,
} from "./admin-page.test-utils"

describe("AdminPage owner workflows", () => {
  it("renders the owner console and drives admin workflows", async () => {
    await renderPage(<AdminPage />)
    await waitForText("Operations Console")
    await waitForText("Gate Draft")

    expect(getContainer().textContent).toContain("Platform Overview")
    expect(getContainer().textContent).toContain("Worker Queues")
    expect(getContainer().textContent).toContain("Redis Key Prefixes")
    expect(getContainer().textContent).toContain("advisor:book")
    expect(getContainer().textContent).toContain("Creator Strikes")
    expect(getContainer().textContent).toContain("Public Demo Books")
    expect(getContainer().textContent).toContain("Subscription Metrics")
    expect(getContainer().textContent).toContain("Admin Access")
    expect(getContainer().textContent).toContain("Audit")
    expect(getContainer().textContent).toContain("Author Monthly")
    expect(getContainer().textContent).toContain("$19/mo")
    expect(getContainer().textContent).toContain("Author Annual")
    expect(getContainer().textContent).toContain("$190/year")
    expect(getContainer().textContent).toContain("Architect Monthly")
    expect(getContainer().textContent).toContain("$39/mo")
    expect(getContainer().textContent).toContain("Architect Annual")
    expect(getContainer().textContent).toContain("$390/year")

    await act(async () => {
      clickButton("Approve", sectionByHeading("Moderation"))
      await flush()
    })
    expect(adminApiMock.reviewPublicShare).toHaveBeenCalledWith("book-1", { approved: true, reason: undefined })

    const moderation = sectionByHeading("Moderation")
    const moderationFields = moderation.querySelectorAll("input,textarea")
    setFieldValue(moderationFields[0] as HTMLInputElement, "book-1")
    setFieldValue(moderationFields[1] as HTMLTextAreaElement, "Policy reason")
    await act(async () => {
      clickButton("hide", moderation)
      await flush()
    })
    expect(adminApiMock.hideBook).toHaveBeenCalledWith("book-1", "Policy reason")

    const rateLimits = sectionByHeading("Rate Limits")
    setFieldValue(rateLimits.querySelector("input") as HTMLInputElement, "user-rate")
    await act(async () => {
      clickButton("Lookup", rateLimits)
      await flush()
    })
    await waitForText("rate@example.com")
    await act(async () => {
      clickButton("Save overrides", rateLimits)
      await flush()
    })
    expect(adminApiMock.setRateLimit).toHaveBeenCalledWith("user-rate", {
      search_per_hour: 10,
      summary_per_hour: null,
      chat_per_day: 5,
      api_per_minute: null,
    })

    const refunds = sectionByHeading("Refunds")
    setFieldValue(refunds.querySelector("textarea") as HTMLTextAreaElement, "Refund reason")
    ;(refunds.querySelector("input[type='checkbox']") as HTMLInputElement).click()
    await act(async () => {
      clickButton("Approve", refunds)
      await flush()
    })
    expect(adminApiMock.approveRefund).toHaveBeenCalledWith("refund-1", {
      reason: "Refund reason",
      provider_followup_only: true,
    })

    const access = sectionByHeading("Admin Access")
    const accessFields = access.querySelectorAll("input,textarea")
    setFieldValue(accessFields[0] as HTMLInputElement, "new-admin")
    setFieldValue(accessFields[1] as HTMLTextAreaElement, "Owner reason")
    await act(async () => {
      clickButton("Grant or update access", access)
      await flush()
    })
    expect(adminApiMock.grantAccess).toHaveBeenCalledWith({
      user_id: "new-admin",
      scopes: ["moderation_admin"],
      is_owner: false,
      reason: "Owner reason",
    })

    await act(async () => {
      clickButton("Revoke", access)
      await flush()
    })
    expect(adminApiMock.revokeAccess).toHaveBeenCalledWith("principal-1", "Owner revoked admin access.")
  })
})
