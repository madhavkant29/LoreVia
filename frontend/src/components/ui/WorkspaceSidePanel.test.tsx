import { act, useState } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"
import { WorkspaceSidePanel } from "@/components/ui/WorkspaceSidePanel"

let root: Root | undefined
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals() })

describe("WorkspaceSidePanel", () => {
  it.each([false, true])("keeps an optional closed panel visible only on desktop (%s)", async (desktop) => {
    vi.stubGlobal("matchMedia", () => ({ matches: desktop, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    const host = document.createElement("div")
    document.body.appendChild(host)
    root = createRoot(host)
    await act(async () => root?.render(<WorkspaceSidePanel title="Library" side="left" open={false} onClose={() => {}}><button>Choose note</button></WorkspaceSidePanel>))
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(document.body.textContent?.includes("Choose note")).toBe(desktop)
  })
  it.each([false, true])("uses a focus-managed dialog only below desktop width (desktop: %s)", async (desktop) => {
    const addEventListener = vi.fn()
    const removeEventListener = vi.fn()
    vi.stubGlobal("matchMedia", () => ({ matches: desktop, addEventListener, removeEventListener }))
    function Harness() {
      const [open, setOpen] = useState(true)
      return open ? <WorkspaceSidePanel title="Manuscript outline" side="left" onClose={() => setOpen(false)}><button>Choose chapter</button></WorkspaceSidePanel> : <p>Draft</p>
    }
    const host = document.createElement("div")
    document.body.appendChild(host)
    root = createRoot(host)
    await act(async () => root?.render(<Harness />))
    expect(Boolean(document.querySelector('[role="dialog"]'))).toBe(!desktop)
    expect(document.body.textContent).toContain("Choose chapter")
    expect(addEventListener).toHaveBeenCalledWith("change", expect.any(Function))
    if (!desktop) {
      const close = [...document.querySelectorAll("button")].find((button) => button.textContent === "Close")
      act(() => close?.click())
      expect(document.querySelector('[role="dialog"]')).toBeNull()
      expect(document.body.textContent).toBe("Draft")
    }
    act(() => root?.unmount())
    root = undefined
    expect(removeEventListener).toHaveBeenCalledWith("change", expect.any(Function))
  })
})
