import { afterEach, describe, expect, it, vi } from "vitest"

const getMock = vi.hoisted(() => vi.fn())
const postMock = vi.hoisted(() => vi.fn())

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
  },
}))

import { emailApi } from "./email"

describe("emailApi", () => {
  afterEach(() => {
    getMock.mockReset()
    postMock.mockReset()
  })

  it("loads authenticated email preferences", async () => {
    getMock.mockResolvedValue({ data: { email: "author@example.com" } })

    await expect(emailApi.getPreferences()).resolves.toEqual({ email: "author@example.com" })
    expect(getMock).toHaveBeenCalledWith("/email/preferences")
  })

  it("updates authenticated email preferences", async () => {
    postMock.mockResolvedValue({ data: { product_updates: false, marketing: true } })

    await expect(
      emailApi.updatePreferences({ product_updates: false, marketing: true })
    ).resolves.toEqual({ product_updates: false, marketing: true })
    expect(postMock).toHaveBeenCalledWith("/email/preferences", {
      product_updates: false,
      marketing: true,
    })
  })
})
