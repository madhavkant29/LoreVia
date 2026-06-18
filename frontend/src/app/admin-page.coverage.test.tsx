// @vitest-environment jsdom

import { act, type ReactElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const adminApiMock = vi.hoisted(() => ({
  access: vi.fn(),
  addStrike: vi.fn(),
  appendPublicDemoChapter: vi.fn(),
  approveRefund: vi.fn(),
  audit: vi.fn(),
  billingStatus: vi.fn(),
  createPublicDemoBook: vi.fn(),
  denyRefund: vi.fn(),
  getRateLimit: vi.fn(),
  grantAccess: vi.fn(),
  hideBook: vi.fn(),
  metrics: vi.fn(),
  publicShares: vi.fn(),
  queueDepth: vi.fn(),
  refunds: vi.fn(),
  removeBook: vi.fn(),
  reports: vi.fn(),
  restoreBook: vi.fn(),
  reviewPublicShare: vi.fn(),
  revokeAccess: vi.fn(),
  session: vi.fn(),
  setRateLimit: vi.fn(),
  stepUp: vi.fn(),
  subscriptionMetrics: vi.fn(),
}))

vi.mock("@/lib/api/admin", () => ({ adminApi: adminApiMock }))

import AdminPage from "@/app/admin/page"

let container: HTMLDivElement | null = null
let root: Root | null = null

const ownerSession = {
  is_admin: true,
  scopes: ["moderation_admin", "billing_admin", "super_admin"],
  is_owner: true,
  requires_step_up: false,
  session_expires_at: "2026-01-02T00:00:00Z",
}

async function renderPage(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

async function waitForText(expected: string) {
  for (let index = 0; index < 40; index += 1) {
    if ((container?.textContent ?? "").includes(expected)) return
    await act(flush)
  }
  throw new Error(`Missing text: ${expected}\n${container?.textContent ?? ""}`)
}

function sectionByHeading(heading: string) {
  const match = Array.from(container?.querySelectorAll("h2,h3") ?? []).find((item) =>
    item.textContent?.includes(heading)
  )
  const section = match?.closest("section")
  if (!section) throw new Error(`Missing section: ${heading}`)
  return section
}

function clickButton(label: string, rootNode: ParentNode = container as ParentNode, index = 0) {
  const matches = Array.from(rootNode.querySelectorAll("button")).filter((button) =>
    button.textContent?.includes(label)
  )
  const button = matches[index]
  if (!button) throw new Error(`Missing button: ${label}`)
  button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
}

function setFieldValue(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

beforeEach(() => {
  adminApiMock.session.mockResolvedValue(ownerSession)
  adminApiMock.publicShares.mockResolvedValue([
    {
      book_id: "book-1",
      user_id: "author-1",
      author_username: "Mira",
      title: "Gate Draft",
      author: "A. Writer",
      genre: "Fantasy",
      copyright_warning: true,
      public_description: "A public preview.",
      requested_at: "2026-01-01T00:00:00Z",
      created_at: "2026-01-01T00:00:00Z",
    },
  ])
  adminApiMock.reports.mockResolvedValue([
    {
      id: "report-1",
      reported_book_id: "book-1",
      reporter_email: "reader@example.com",
      report_type: "copyright",
      status: "open",
      reason: "Copied chapter",
      details: "The sample appears duplicated.",
      created_at: "2026-01-01T00:00:00Z",
    },
  ])
  adminApiMock.billingStatus.mockResolvedValue({
    billing_enabled: true,
    payments_ready: false,
    paddle_api_key_present: true,
    webhook_secret_present: false,
    default_checkout_url_present: true,
    recommended_default_checkout_url: "https://checkout.example",
    resend_api_key_present: true,
    internal_job_secret_present: true,
    fully_configured_plan_count: 2,
    missing_configuration: ["PADDLE_WEBHOOK_SECRET"],
    plans: [],
    webhook_endpoint_path: "/api/webhooks/paddle",
    supported_webhook_events: ["subscription.created"],
    trial_email_job_endpoint_path: "/api/jobs/trials",
    trial_email_runner_script: "run-trials",
    trial_email_automation_code_ready: true,
    priority_processing_code_ready: true,
    priority_queue_names: ["priority"],
    external_action_items: [],
  })
  adminApiMock.refunds.mockResolvedValue([
    {
      id: "refund-1",
      user_id: "user-1",
      paddle_transaction_id: "txn-1",
      charge_at: "2026-01-01T00:00:00Z",
      plan_code: "architect",
      billing_interval: "monthly",
      request_source: "support",
      request_reason: "Duplicate charge",
      status: "pending",
      eligibility_snapshot_json: {},
      usage_snapshot_json: {},
      provider_response_json: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ])
  adminApiMock.metrics.mockResolvedValue({
    users: 10,
    books: 20,
    characters: 30,
    chunks_indexed: 40,
    summaries_cached: 50,
    redis_memory_mb: 12,
  })
  adminApiMock.queueDepth.mockResolvedValue({
    extraction: 4,
    analysis: 3,
    embedding: 2,
    intelligence: 1,
  })
  adminApiMock.subscriptionMetrics.mockResolvedValue({
    cohort_start: "2026-01-01",
    cohort_end: "2026-01-31",
    trial_starts: 9,
    trial_to_paid_conversions: 3,
    trial_to_paid_rate: 0.333,
    cancellation_events: 2,
    resolved_cancellation_events: 1,
    unresolved_cancellation_events: 1,
    reactivated_after_cancellation: 1,
    churned_after_cancellation: 1,
    post_cancel_churn_rate: 0.5,
    reactivation_window_days: 30,
  })
  adminApiMock.access.mockResolvedValue([
    {
      id: "principal-1",
      user_id: "admin-user",
      status: "active",
      is_owner: false,
      scopes: ["moderation_admin"],
      grant_reason: "Coverage fixture",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ])
  adminApiMock.audit.mockResolvedValue([
    {
      id: "audit-1",
      action_type: "grant_access",
      reason: "Coverage fixture",
      result: "success",
      scopes_snapshot: ["moderation_admin"],
      metadata_json: {},
      created_at: "2026-01-01T00:00:00Z",
    },
  ])
  adminApiMock.getRateLimit.mockResolvedValue({
    user_id: "user-rate",
    email: "rate@example.com",
    override: {
      search_per_hour: 10,
      summary_per_hour: null,
      chat_per_day: 5,
      api_per_minute: null,
    },
  })
  adminApiMock.reviewPublicShare.mockResolvedValue({})
  adminApiMock.hideBook.mockResolvedValue({})
  adminApiMock.removeBook.mockResolvedValue({})
  adminApiMock.restoreBook.mockResolvedValue({})
  adminApiMock.approveRefund.mockResolvedValue({})
  adminApiMock.denyRefund.mockResolvedValue({})
  adminApiMock.grantAccess.mockResolvedValue({})
  adminApiMock.revokeAccess.mockResolvedValue({})
  adminApiMock.setRateLimit.mockResolvedValue({})
  adminApiMock.addStrike.mockResolvedValue({})
  adminApiMock.createPublicDemoBook.mockResolvedValue({ book_id: "book-new" })
  adminApiMock.appendPublicDemoChapter.mockResolvedValue({ book_id: "book-1", chapter_number: 2, saved: true })
  adminApiMock.stepUp.mockResolvedValue({ ok: true })
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
  vi.clearAllMocks()
})

describe("AdminPage", () => {
  it("renders the owner console and drives admin workflows", async () => {
    await renderPage(<AdminPage />)
    await waitForText("Operations Console")
    await waitForText("Gate Draft")

    expect(container?.textContent).toContain("Platform Overview")
    expect(container?.textContent).toContain("Worker Queues")
    expect(container?.textContent).toContain("Creator Strikes")
    expect(container?.textContent).toContain("Public Demo Books")
    expect(container?.textContent).toContain("Subscription Metrics")
    expect(container?.textContent).toContain("Admin Access")
    expect(container?.textContent).toContain("Audit")

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

  it("handles step-up verification and missing admin access", async () => {
    adminApiMock.session
      .mockResolvedValueOnce({ ...ownerSession, requires_step_up: true })
      .mockResolvedValueOnce(ownerSession)
    await renderPage(<AdminPage />)
    await waitForText("Verify password")

    setFieldValue(container?.querySelector("input[type='password']") as HTMLInputElement, "secret")
    await act(async () => {
      clickButton("Verify")
      await flush()
    })
    expect(adminApiMock.stepUp).toHaveBeenCalledWith("secret")

    root?.unmount()
    container?.remove()
    container = null
    root = null
    adminApiMock.session.mockRejectedValueOnce(new Error("not found"))
    await renderPage(<AdminPage />)
    await waitForText("404")
    expect(container?.textContent).toContain("Not found.")
  })
})
