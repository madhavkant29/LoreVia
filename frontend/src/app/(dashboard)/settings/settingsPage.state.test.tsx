// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, expect, it, vi } from "vitest"
import { useSettingsDraftGuard, useSettingsResource } from "./settingsPage.state"

let root: Root | undefined
let host: HTMLDivElement | undefined
let current: ReturnType<typeof useSettingsResource<string>>
let leave: () => boolean
function Harness({ account, load, dirty = false, busy = false }: { account?: string; load: () => Promise<string>; dirty?: boolean; busy?: boolean }) {
  current = useSettingsResource(account, load)
  leave = useSettingsDraftGuard(dirty, busy)
  return <a href="/library">Library</a>
}
async function render(props: Parameters<typeof Harness>[0]) {
  if (!host) { host = document.createElement("div"); document.body.append(host); root = createRoot(host) }
  await act(async () => { root?.render(<Harness {...props} />) })
}
afterEach(() => { act(() => root?.unmount()); host?.remove(); root = undefined; host = undefined; vi.restoreAllMocks() })

it("does not request settings before identity is available and retries a failed resource", async () => {
  const load = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue("confirmed")
  await render({ load })
  expect(load).not.toHaveBeenCalled()
  await render({ load, account: "author" })
  expect(current.failed).toBe(true)
  expect(current.data).toBeNull()
  await act(async () => current.retry())
  expect(current.failed).toBe(false)
  expect(current.data).toBe("confirmed")
})

it("ignores an obsolete account request that completes after a new account loads", async () => {
  let finish: (value: string) => void = () => {}
  const load = vi.fn().mockImplementationOnce(() => new Promise<string>((resolve) => { finish = resolve })).mockResolvedValue("new account")
  await render({ load, account: "first" })
  expect(current.loading).toBe(true)
  await render({ load, account: "second" })
  await act(async () => finish("old account"))
  expect(current.data).toBe("new account")
})

it("guards unsaved settings and pending writes and respects a confirmed departure", async () => {
  const load = vi.fn().mockResolvedValue("data")
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
  await render({ load, account: "author", dirty: true })
  const event = new MouseEvent("click", { cancelable: true, bubbles: true })
  host?.querySelector("a")?.dispatchEvent(event)
  expect(event.defaultPrevented).toBe(true)
  expect(confirm).toHaveBeenCalledOnce()
  const unload = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(unload)
  expect(unload.defaultPrevented).toBe(true)
  confirm.mockReturnValue(true)
  expect(leave()).toBe(true)
  const allowed = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(allowed)
  expect(allowed.defaultPrevented).toBe(false)
  await render({ load, account: "author", busy: true })
  expect(leave()).toBe(false)
})
