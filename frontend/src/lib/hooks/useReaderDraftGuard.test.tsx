import { act } from "react"
import { createRoot } from "react-dom/client"
import { expect, it, vi } from "vitest"
import { useReaderDraftGuard } from "./useReaderDraftGuard"

it("guards unsaved reading notes and prevents dismissal during a save", () => {
  const element = document.createElement("div"); document.body.append(element)
  const root = createRoot(element)
  let canLeave: () => boolean = () => true
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
  function View({ dirty, busy }: { dirty: boolean; busy: boolean }) { canLeave = useReaderDraftGuard(dirty, busy); return <a href="/another-chapter">Next</a> }
  act(() => root.render(<View dirty busy={false} />))
  expect(canLeave()).toBe(false)
  const unload = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(unload); expect(unload.defaultPrevented).toBe(true)
  const navigation = new MouseEvent("click", { bubbles: true, cancelable: true }); element.querySelector("a")?.dispatchEvent(navigation); expect(navigation.defaultPrevented).toBe(true)
  confirm.mockReturnValue(true); expect(canLeave()).toBe(true)
  act(() => root.render(<View dirty={false} busy />)); expect(canLeave()).toBe(false)
  act(() => root.render(<View dirty={false} busy={false} />)); expect(canLeave()).toBe(true)
  act(() => root.unmount()); element.remove(); confirm.mockRestore()
})
