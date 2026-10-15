// @vitest-environment jsdom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ProcessingStatusPanel, ProcessingStatusStrip } from "./ResponsivenessStatus"
import { normalizeProcessingStatus } from "@/lib/utils/processingStatus"

let root: Root | null = null
let container: HTMLDivElement | null = null

function render(element: React.ReactNode) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(element)
  })
  return container
}

afterEach(() => {
  act(() => {
    root?.unmount()
  })
  container?.remove()
  container = null
  root = null
})

const frozenStatus = normalizeProcessingStatus({
  status: "failed",
  stage: "frozen",
  frozen: true,
  freeze_message:
    "Import interrupted - please upload again. Your project and files have been preserved.",
  retry_actions: [],
})

describe("frozen processing status surfaces", () => {
  it("shows the interrupt message with a fresh-upload action instead of retry", () => {
    const onRetry = vi.fn()
    const view = render(<ProcessingStatusPanel status={frozenStatus} onRetry={onRetry} />)

    expect(view.textContent).toContain("Import interrupted")
    expect(view.textContent).toContain("upload again")
    expect(view.textContent).not.toContain("Retry")
    const link = view.querySelector('a[href="/library"]')
    expect(link).not.toBeNull()
    expect(link?.textContent).toContain("Upload again")
    // No progress bar is rendered for a frozen import.
    expect(view.querySelector(".animate-pulse")).toBeNull()
    expect(onRetry).not.toHaveBeenCalled()
  })

  it("renders the strip variant without a retry button for frozen statuses", () => {
    const onRetry = vi.fn()
    const view = render(<ProcessingStatusStrip status={frozenStatus} onRetry={onRetry} />)

    expect(view.textContent).toContain("Import interrupted")
    expect(view.textContent).not.toContain("Retry")
    expect(view.querySelector('a[href="/library"]')).not.toBeNull()
  })

  it("keeps the retry button for ordinary recoverable failures", () => {
    const recoverable = normalizeProcessingStatus({ status: "failed", stage: "failed" })
    const onRetry = vi.fn()
    const view = render(<ProcessingStatusPanel status={recoverable} onRetry={onRetry} />)

    expect(view.textContent).toContain("Retry processing")
    expect(view.querySelector('a[href="/library"]')).toBeNull()
  })
})
