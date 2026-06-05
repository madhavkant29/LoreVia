// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ActionableEmptyState } from "../ActionableEmptyState"
import { ConfirmDialog } from "../ConfirmDialog"
import { MobileActionBar } from "../MobileActionBar"
import { StatusToastProvider, useStatusToast } from "../StatusToast"

let container: HTMLDivElement | null = null
let root: Root | null = null

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  container = null
  root = null
  document.body.innerHTML = ""
  vi.useRealTimers()
})

function render(element: ReactNode) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(element)
  })
  return container
}

describe("UX primitives", () => {
  it("renders actionable empty state actions", () => {
    const onClick = vi.fn()
    const rendered = render(
      <ActionableEmptyState
        title="No projects yet"
        body="Start by creating a project."
        actions={[{ label: "New Project", onClick, tone: "primary" }]}
      />,
    )

    const button = rendered.querySelector("button")
    expect(rendered.textContent).toContain("No projects yet")
    expect(button?.textContent).toContain("New Project")
    act(() => button?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(onClick).toHaveBeenCalled()
  })

  it("confirms destructive actions through the dialog", () => {
    const resolve = vi.fn()
    const rendered = render(
      <ConfirmDialog
        pending={{
          title: "Delete note?",
          body: "Delete Draft.md?",
          confirmLabel: "Delete note",
          tone: "danger",
          resolve,
        }}
        onClose={resolve}
      />,
    )

    expect(rendered.querySelector('[role="dialog"]')?.textContent).toContain("Delete note?")
    const buttons = Array.from(rendered.querySelectorAll("button"))
    act(() => buttons[1]?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(resolve).toHaveBeenCalledWith(true)
  })

  it("renders mobile action bar actions", () => {
    const onSelect = vi.fn()
    const rendered = render(<MobileActionBar actions={[{ id: "summary", label: "Summary", onSelect }]} />)
    const button = rendered.querySelector("button")

    expect(button?.textContent).toContain("Summary")
    act(() => button?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(onSelect).toHaveBeenCalled()
  })

  it("shows status toast messages from the provider", () => {
    function Demo() {
      const notify = useStatusToast()
      return <button type="button" onClick={() => notify({ body: "Saved draft.", tone: "success" })}>Notify</button>
    }

    const rendered = render(
      <StatusToastProvider>
        <Demo />
      </StatusToastProvider>,
    )
    act(() => rendered.querySelector("button")?.dispatchEvent(new MouseEvent("click", { bubbles: true })))

    expect(rendered.textContent).toContain("Saved draft.")
  })
})
