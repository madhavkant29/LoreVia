import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

import { ContextualUpgradePrompt } from "./ContextualUpgradePrompt"

let container: HTMLDivElement | null = null
let root: Root | null = null

function renderPrompt(onBack = vi.fn()) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <ContextualUpgradePrompt
        featureName="Manuscript Editor"
        body="Free includes reading existing projects, exporting manuscript and novel files, and 1 Story Advisor turn each week."
        onBack={onBack}
      />
    )
  })

  return { view: container, onBack }
}

describe("ContextualUpgradePrompt", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    container?.remove()
    container = null
    root = null
  })

  it("renders a compact upgrade path for blocked author features", () => {
    const { view, onBack } = renderPrompt()

    expect(view.textContent).toContain("Manuscript Editor requires Author")
    expect(view.textContent).toContain("1 Story Advisor turn each week")
    expect(view.querySelector('a[href="/upgrade?plan=author"]')?.textContent).toBe("Upgrade to Author")
    expect(view.querySelector('a[href="/upgrade"]')?.textContent).toBe("Compare plans")

    const backButton = Array.from(view.querySelectorAll("button")).find((button) => button.textContent === "Back")
    act(() => {
      backButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(onBack).toHaveBeenCalledTimes(1)
  })
})
