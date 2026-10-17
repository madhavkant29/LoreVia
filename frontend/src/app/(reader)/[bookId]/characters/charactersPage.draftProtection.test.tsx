// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useCharacterDraftProtection } from "./charactersPage.draftProtection"
import { buildCreateDraft, buildDraft } from "./charactersPage.helpers"
import { character } from "./charactersPage.testData"
const push = vi.hoisted(() => vi.fn())
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))

let root: Root
let container: HTMLDivElement
let change: ReturnType<typeof useCharacterDraftProtection>
const record = character({})
const confirm = vi.fn()
const onDiscard = vi.fn()
function render(overrides: Partial<Parameters<typeof useCharacterDraftProtection>[0]> = {}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  function Harness() {
    change = useCharacterDraftProtection({ editing: true, creating: false, draft: { ...buildDraft(record), name: "New name" }, createDraft: buildCreateDraft(1), character: record, busy: false, confirm, onDiscard, ...overrides })
    return null
  }
  act(() => root.render(<Harness />))
}
afterEach(() => { act(() => root?.unmount()); container?.remove(); vi.resetAllMocks() })

describe("character draft protection", () => {
  it("keeps edits when discard is cancelled and prevents unloading", async () => {
    confirm.mockResolvedValue(false)
    render()
    const next = vi.fn()
    expect(await change(next)).toBe(false)
    expect(next).not.toHaveBeenCalled()
    expect(onDiscard).not.toHaveBeenCalled()
    const unload = new Event("beforeunload", { cancelable: true })
    window.dispatchEvent(unload)
    expect(unload.defaultPrevented).toBe(true)
  })
  it("discards only after approval, then changes the workspace", async () => {
    confirm.mockResolvedValue(true)
    render()
    const next = vi.fn()
    expect(await change(next)).toBe(true)
    expect(onDiscard).toHaveBeenCalledOnce()
    expect(next).toHaveBeenCalledOnce()
  })
  it("allows an unchanged profile without confirmation and blocks transitions while saving", async () => {
    render({ draft: buildDraft(record), busy: true })
    const next = vi.fn()
    expect(await change(next)).toBe(false)
    expect(confirm).not.toHaveBeenCalled()
    expect(next).not.toHaveBeenCalled()
  })
  it("allows an empty new form without confirmation", async () => {
    render({ editing: false, creating: true })
    const next = vi.fn()
    expect(await change(next)).toBe(true)
    expect(confirm).not.toHaveBeenCalled()
  })
  it("protects a new named character", async () => {
    confirm.mockResolvedValue(false)
    render({ editing: false, creating: true, createDraft: { ...buildCreateDraft(1), name: "Nora" } })
    expect(await change(vi.fn())).toBe(false)
    expect(confirm).toHaveBeenCalledOnce()
  })
  it("protects chapter-only changes in a new form", async () => {
    confirm.mockResolvedValue(false)
    render({ editing: false, creating: true, createDraft: { ...buildCreateDraft(1), firstChapter: "5" } })
    expect(await change(vi.fn())).toBe(false)
    expect(confirm).toHaveBeenCalledOnce()
  })
  it("keeps internal navigation pending until discard is confirmed", async () => {
    render()
    const link = document.createElement("a")
    link.href = "/library"
    container.appendChild(link)
    confirm.mockResolvedValueOnce(false)
    await act(async () => link.click())
    expect(push).not.toHaveBeenCalled()
    confirm.mockResolvedValueOnce(true)
    await act(async () => link.click())
    expect(push).toHaveBeenCalledWith("/library")
  })
})
