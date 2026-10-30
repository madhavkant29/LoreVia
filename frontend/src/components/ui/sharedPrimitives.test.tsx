// @vitest-environment jsdom

import { act, useRef, useState, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { Button } from "./Button"
import { Dialog } from "./Dialog"
import { DisclosureMenu } from "./DisclosureMenu"
import { MobileActionBar } from "./MobileActionBar"

let root: Root | null = null
let container: HTMLDivElement | null = null

function DialogHarness() {
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Open dialog</button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Accessible dialog"
        description="Dialog description"
        initialFocusRef={inputRef}
        footer={<Button onClick={() => setOpen(false)}>Done</Button>}
      >
        <input ref={inputRef} aria-label="Dialog field" />
      </Dialog>
    </>
  )
}

async function render(element: ReactNode) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

async function click(element: Element | null) {
  if (!(element instanceof HTMLElement)) throw new Error("Missing click target")
  await act(async () => {
    element.click()
    await Promise.resolve()
  })
}

async function pointerDown(element: Element | null) {
  if (!(element instanceof HTMLElement)) throw new Error("Missing pointer target")
  await act(async () => {
    element.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, button: 0 }))
    await Promise.resolve()
  })
}

beforeEach(() => {
  ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  Object.defineProperties(HTMLElement.prototype, {
    hasPointerCapture: { configurable: true, value: vi.fn(() => false) },
    setPointerCapture: { configurable: true, value: vi.fn() },
    releasePointerCapture: { configurable: true, value: vi.fn() },
    scrollIntoView: { configurable: true, value: vi.fn() },
  })
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  })
})

afterEach(() => {
  if (root) act(() => root?.unmount())
  root = null
  container?.remove()
  container = null
  document.body.innerHTML = ""
  vi.unstubAllGlobals()
})

describe("shared accessible primitives", () => {
  it("exposes explicit focus, disabled, and reduced-motion states on primary controls", async () => {
    await render(<Button disabled>Unavailable</Button>)
    const button = container?.querySelector("button") as HTMLButtonElement

    expect(button.disabled).toBe(true)
    expect(button.className).toContain("focus-visible:ring-2")
    expect(button.className).toContain("disabled:opacity-50")
    expect(button.className).toContain("motion-reduce:transition-none")
  })

  it("traps dialog focus, closes with Escape, and restores the trigger", async () => {
    await render(<DialogHarness />)
    const trigger = container?.querySelector("button") as HTMLButtonElement
    trigger.focus()
    await click(trigger)

    const field = document.querySelector('[aria-label="Dialog field"]') as HTMLInputElement
    expect(document.querySelector('[role="dialog"]')).not.toBeNull()
    expect(document.activeElement).toBe(field)

    const done = Array.from(document.querySelectorAll("button")).find((button) => button.textContent === "Done") as HTMLButtonElement
    done.focus()
    await act(async () => {
      done.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }))
      await Promise.resolve()
    })
    expect(document.activeElement).toBe(field)

    await act(async () => {
      field.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
      await Promise.resolve()
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })

  it("keeps disclosure menus open until selection or Escape", async () => {
    await render(
      <DisclosureMenu
        label="More actions"
        trigger={<span>More</span>}
        items={[
          { id: "one", label: "First action", onSelect: vi.fn() },
          { id: "two", label: "Second action" },
        ]}
      />,
    )
    const trigger = container?.querySelector("button") as HTMLButtonElement
    trigger.focus()
    await pointerDown(trigger)

    expect(trigger.getAttribute("aria-expanded")).toBe("true")
    const menu = document.querySelector('[role="menu"]')
    expect(menu?.textContent).toContain("First action")

    await act(async () => {
      menu?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
      await Promise.resolve()
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
    expect(document.querySelector('[role="menu"]')).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })

  it("limits mobile primary actions and recovers overflow actions from More", async () => {
    await render(
      <MobileActionBar
        actions={[
          { id: "one", label: "First", onSelect: vi.fn() },
          { id: "two", label: "Second", onSelect: vi.fn() },
          { id: "three", label: "Third", onSelect: vi.fn() },
        ]}
        moreActions={[{ id: "hidden", label: "Show hidden tools", onSelect: vi.fn() }]}
      />,
    )

    expect(container?.textContent).toContain("First")
    expect(container?.textContent).toContain("Second")
    expect(container?.textContent).not.toContain("Third")
    const more = container?.querySelector('[aria-label="More actions"]')
    await pointerDown(more ?? null)
    expect(document.querySelector('[role="menu"]')?.textContent).toContain("Third")
    expect(document.querySelector('[role="menu"]')?.textContent).toContain("Show hidden tools")
  })
})
