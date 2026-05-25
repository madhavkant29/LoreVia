import { beforeEach, describe, expect, it, vi } from "vitest"

const { getMock, postMock, putMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    put: putMock,
  },
}))

import { adminApi } from "./admin"

describe("admin api", () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()
    getMock.mockResolvedValue({ data: { ok: true } })
    postMock.mockResolvedValue({ data: { ok: true } })
    putMock.mockResolvedValue({ data: { ok: true } })
  })

  it("loads admin session and billing status from admin routes", async () => {
    await adminApi.session()
    await adminApi.billingStatus()

    expect(getMock).toHaveBeenCalledWith("/admin/session")
    expect(getMock).toHaveBeenCalledWith("/admin/billing/status")
  })

  it("uses capped list endpoints for access and public shares", async () => {
    await adminApi.access()
    await adminApi.publicShares()

    expect(getMock).toHaveBeenCalledWith("/admin/access?limit=50")
    expect(getMock).toHaveBeenCalledWith("/admin/public-shares/pending?limit=50")
  })

  it("sends provider follow-up approval decisions through the admin refund route", async () => {
    await adminApi.approveRefund("review-1", {
      reason: "Unsafe linkage requires provider follow-up.",
      provider_followup_only: true,
    })

    expect(postMock).toHaveBeenCalledWith("/admin/refunds/reviews/review-1/approve", {
      reason: "Unsafe linkage requires provider follow-up.",
      provider_followup_only: true,
    })
  })
})
