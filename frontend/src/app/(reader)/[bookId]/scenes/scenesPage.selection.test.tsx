import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useSceneSelectionMenu } from "./scenesPage.selection"
import type { Character } from "@/types/character"

vi.mock("@/components/characters/AddCharacterFromSelection", () => ({ AddCharacterFromSelection: () => null }))
let root: Root | undefined
let current: ReturnType<typeof useSceneSelectionMenu>
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.restoreAllMocks() })

describe("scene selection actions", () => {
  it("ignores empty selections and positions selected text in viewport coordinates", async () => {
    const setStatus = vi.fn()
    function Harness() { current = useSceneSelectionMenu(setStatus); return <div data-editor-key="scene-workspace-editor">Nora</div> }
    const host = document.createElement("div")
    document.body.appendChild(host)
    root = createRoot(host)
    await act(async () => root?.render(<Harness />))
    act(() => current.openAddCharacterFromSelection())
    expect(setStatus).toHaveBeenCalledWith("Select a character name in the scene first.")
    const text = host.firstChild!.firstChild!
    vi.spyOn(window, "getSelection").mockReturnValue({
      anchorNode: text, rangeCount: 1, toString: () => " Nora ",
      getRangeAt: () => ({ getBoundingClientRect: () => ({ top: 100, left: 2000, width: 40, height: 20 }) }),
    } as unknown as Selection)
    act(() => document.dispatchEvent(new Event("selectionchange")))
    expect(current.selectionMenu).toMatchObject({ text: "Nora", top: 52, left: window.innerWidth - 100 })
    act(() => current.openAddCharacterFromSelection())
    expect(current.addCharacterOpen).toBe(true)
    expect(current.addCharacterText).toBe("Nora")
    expect(current.selectionMenu).toBeNull()
    act(() => current.handleCharacterCreated({ name: "Nora" } as Character))
    expect(setStatus).toHaveBeenLastCalledWith('Character "Nora" added to the story bible.')
  })
})
