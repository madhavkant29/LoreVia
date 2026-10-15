// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ActionableEmptyState } from "../ActionableEmptyState"
import { ConfirmDialog } from "../ConfirmDialog"
import { MobileActionBar } from "../MobileActionBar"
import { ProcessingStatusStrip, SaveStatePill } from "../ResponsivenessStatus"
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
    render(
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

    expect(document.body.querySelector('[role="dialog"]')?.textContent).toContain("Delete note?")
    const buttons = Array.from(document.body.querySelectorAll("button"))
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

  it("renders processing status with retry action", () => {
    const onRetry = vi.fn()
    const rendered = render(
      <ProcessingStatusStrip
        status={{
          stage: "failed",
          label: "Processing failed",
          detail: "Retry is available",
          progressPct: 64,
          chaptersCompleted: 4,
          chaptersTotal: 6,
          lastError: "Worker failed",
          retryAvailable: true,
          partialReady: false,
          ready: false,
          failed: true,
          frozen: false,
          failureKind: "recoverable",
          stateVariant: "recoverable_failure",
        }}
        onRetry={onRetry}
      />
    )

    expect(rendered.textContent).toContain("Processing failed")
    const button = rendered.querySelector("button")
    expect(button?.textContent).toContain("Retry")
    act(() => button?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(onRetry).toHaveBeenCalled()
  })

  it("labels allowance-paused processing as continuable", () => {
    const rendered = render(
      <ProcessingStatusStrip
        status={{
          stage: "queued",
          label: "Processing paused",
          detail: "Monthly allowance reached",
          progressPct: 50,
          chaptersCompleted: 1,
          chaptersTotal: 3,
          lastError: null,
          retryAvailable: true,
          resumeAvailable: true,
          partialReady: true,
          ready: false,
          failed: false,
          frozen: false,
          failureKind: null,
          stateVariant: "partial_ready",
        }}
        onRetry={() => undefined}
      />
    )

    expect(rendered.querySelector("button")?.textContent).toContain("Continue processing")
  })

  it("shows auto-resume token pauses without a manual action", () => {
    const rendered = render(
      <ProcessingStatusStrip
        status={{
          stage: "extracting",
          label: "Processing paused",
          detail: "Token limit reached. Reprocessing will resume automatically around 5:30 PM.",
          progressPct: 50,
          chaptersCompleted: 1,
          chaptersTotal: 2,
          lastError: null,
          retryAvailable: false,
          resumeAvailable: false,
          autoResume: true,
          partialReady: true,
          ready: false,
          failed: false,
          frozen: false,
          failureKind: null,
          stateVariant: "partial_ready",
        }}
        onRetry={() => undefined}
      />
    )

    expect(rendered.textContent).toContain("resume automatically")
    expect(rendered.querySelector("button")).toBeNull()
  })

  it("renders standardized save state copy", () => {
    const rendered = render(<SaveStatePill state="offline_draft" />)
    expect(rendered.textContent).toContain("Offline draft")
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
