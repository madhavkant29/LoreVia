import { act, useRef, useState } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { VaultNote } from "@/types/book"
import { useVaultNotesAutosave } from "./VaultNotesEditor.autosave"

const { save, push } = vi.hoisted(() => ({ save: vi.fn(), push: vi.fn() }))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))
vi.mock("@/lib/api/books", () => ({ booksApi: { saveVaultNote: save } }))
let root: Root
let value: ReturnType<typeof useVaultNotesAutosave>
let currentNotes: VaultNote[]
const seed = [{ path: "A.md", content: "Original", updated_at: "2026-01-01" }, { path: "B.md", content: "Other" }] as VaultNote[]
function Harness() {
  const [notes, setNotes] = useState(seed)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const latestDraftRef = useRef<Record<string, string>>({})
  value = useVaultNotesAutosave({ bookId: "book", notes, drafts, latestDraftRef, busy: false, setNotes, setDrafts })
  currentNotes = notes
  return <a href="/library">Library</a>
}
beforeEach(async () => {
  vi.useFakeTimers(); vi.clearAllMocks(); sessionStorage.clear()
  save.mockImplementation(async (_book, payload) => ({ ...payload, updated_at: "2026-02-01" }))
  const host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); document.body.innerHTML = ""; vi.useRealTimers() })
async function mount() { await act(async () => root.render(<Harness />)) }
async function edit(content: string, path = "A.md") { await act(async () => value.updateDraft(path, content)) }
async function tick() { await act(async () => vi.advanceTimersByTimeAsync(701)) }

describe("note autosave", () => {
  it("debounces edits and backs up the latest unsaved draft before the network write", async () => {
    await mount(); await edit("First"); await edit("Latest")
    expect(save).not.toHaveBeenCalled()
    expect(JSON.parse(sessionStorage.getItem("lorevia:note-drafts:book")!)).toEqual({ "A.md": "Latest" })
    await tick()
    expect(save).toHaveBeenCalledTimes(1)
    expect(currentNotes[0].content).toBe("Latest")
    expect(value.dirty).toBe(false)
    expect(sessionStorage.getItem("lorevia:note-drafts:book")).toBeNull()
  })
  it("serializes delayed writes and retains newer typing while the first save resolves", async () => {
    let resolve!: (value: unknown) => void
    save.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    await mount(); await edit("First"); await tick(); await edit("Newest"); await tick()
    expect(save).toHaveBeenCalledTimes(1)
    await act(async () => { resolve({ path: "A.md", content: "First" }); await Promise.resolve() })
    expect(save).toHaveBeenCalledTimes(2)
    expect(save.mock.calls[1][1].content).toBe("Newest")
    expect(currentNotes[0].content).toBe("Newest")
    expect(value.dirty).toBe(false)
  })
  it("keeps a failed draft and retries it without an automatic retry loop", async () => {
    save.mockRejectedValueOnce(new Error("offline"))
    await mount(); await edit(""); await tick(); await tick()
    expect(save).toHaveBeenCalledTimes(1)
    expect(value.errors["A.md"]).toContain("Your draft is still here")
    expect(value.dirty).toBe(true)
    await act(async () => { expect(await value.flushAll()).toBe(true) })
    expect(currentNotes[0].content).toBe("")
    expect(value.errors).toEqual({})
  })
  it("cancels pending saves before deletion and forgets deleted draft backups", async () => {
    await mount(); await edit("Pending")
    await act(async () => { await value.settlePath("A.md"); value.forgetPath("A.md") })
    await tick()
    expect(save).not.toHaveBeenCalled()
    expect(sessionStorage.getItem("lorevia:note-drafts:book")).toBeNull()
  })
  it("saves all edited notes before internal navigation and stays on failure", async () => {
    await mount(); await edit("A change"); await edit("B change", "B.md")
    save.mockRejectedValueOnce(new Error("offline"))
    await act(async () => document.querySelector("a")!.click())
    expect(push).not.toHaveBeenCalled()
    await act(async () => document.querySelector("a")!.click())
    expect(push).toHaveBeenCalledWith("/library")
    expect(currentNotes.map((note) => note.content)).toEqual(["A change", "B change"])
  })
  it("waits for an in-flight save before allowing a path mutation", async () => {
    let resolve!: (value: unknown) => void
    save.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    await mount(); await edit("In flight"); await tick()
    let settled = false
    const pending = value.settlePath("A.md").then(() => { settled = true })
    expect(settled).toBe(false)
    await act(async () => { resolve({ path: "A.md", content: "In flight" }); await pending })
    expect(settled).toBe(true)
  })
  it("warns before unloading an unsaved draft but not after saving", async () => {
    await mount(); await edit("Pending")
    const before = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(before)
    expect(before.defaultPrevented).toBe(true)
    await tick()
    const after = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(after)
    expect(after.defaultPrevented).toBe(false)
  })
  it("restores valid tab drafts for existing notes without overwriting the server automatically", async () => {
    sessionStorage.setItem("lorevia:note-drafts:book", JSON.stringify({ "A.md": "Recovered", "Missing.md": "Ignored", "B.md": null }))
    await mount(); await tick()
    expect(value.recovered).toBe(true); expect(value.dirty).toBe(true); expect(save).not.toHaveBeenCalled()
    await act(async () => { await value.flushAll() })
    expect(currentNotes[0].content).toBe("Recovered")
  })
  it("ignores malformed recovery data", async () => {
    sessionStorage.setItem("lorevia:note-drafts:book", "not-json")
    await mount()
    expect(value.recovered).toBe(false); expect(value.dirty).toBe(false)
  })
  it("clears stale failure feedback when the author restores the saved content", async () => {
    save.mockRejectedValueOnce(new Error("offline"))
    await mount(); await edit("Failed change"); await tick()
    await edit("Original"); await tick()
    expect(value.errors).toEqual({}); expect(value.dirty).toBe(false)
    expect(save).toHaveBeenCalledTimes(1)
  })
  it("reports unavailable tab backups without preventing a server save", async () => {
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Quota exceeded") })
    await mount(); await edit("Still saveable")
    expect(value.backupUnavailable).toBe(true)
    write.mockRestore()
    await tick()
    expect(currentNotes[0].content).toBe("Still saveable")
    expect(value.backupUnavailable).toBe(false)
  })
})
