import { describe, expect, it, vi } from "vitest"

import { preventProtectedManuscriptCopy, PRIVATE_SHARE_COPY_NOTICE } from "@/lib/utils/manuscriptCopyProtection"

describe("manuscript copy protection", () => {
  it("allows copy when manuscript copy is permitted", () => {
    const event = { preventDefault: vi.fn() }

    expect(preventProtectedManuscriptCopy(event, true)).toBe(false)
    expect(event.preventDefault).not.toHaveBeenCalled()
  })

  it("blocks copy when manuscript copy is disabled", () => {
    const event = { preventDefault: vi.fn() }

    expect(preventProtectedManuscriptCopy(event, false)).toBe(true)
    expect(event.preventDefault).toHaveBeenCalledOnce()
    expect(PRIVATE_SHARE_COPY_NOTICE).toContain("private manuscript share")
  })
})
