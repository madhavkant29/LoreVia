import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { DemoWorkspace } from "./DemoWorkspace"

vi.mock("next/image", () => ({
  default: ({ priority: _priority, alt = "", ...props }: React.ImgHTMLAttributes<HTMLImageElement> & { priority?: boolean }) => <img alt={alt} {...props} />,
}))
vi.mock("@/lib/analytics/posthog", () => ({ capture: vi.fn() }))

describe("DemoWorkspace", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it("updates and resets the revision plan without an API", () => {
    act(() => root.render(<DemoWorkspace />))
    const accept = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Add to revision plan")
    act(() => accept?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(container.textContent).toContain("1/3 reviewed")
    expect(container.textContent).toContain("Jonathan's arrival timing conflicts")

    const reset = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Reset demo")
    act(() => reset?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(container.textContent).toContain("0/3 reviewed")
    expect(container.textContent).toContain("Accepted findings appear here")
  })
})
