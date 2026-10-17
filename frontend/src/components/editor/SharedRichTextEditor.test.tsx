import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

type EditorConfiguration = {
  editorProps: { attributes: Record<string, string> }
  onUpdate: (event: { editor: { getHTML: () => string; getText: () => string } }) => void
}
const state = vi.hoisted(() => ({ config: null as EditorConfiguration | null, editor: { commands: { setContent: vi.fn() } } }))
vi.mock("@tiptap/react", () => ({
  useEditor: (config: EditorConfiguration) => { state.config = config; return state.editor },
  EditorContent: () => <div />,
}))
import { EditorToolbar, RichTextEditor } from "./SharedRichTextEditor"

let root: Root | undefined
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.clearAllMocks() })

describe("external rich text content", () => {
  it("puts extra formatting outside a clipping toolbar and dismisses it with Escape", async () => {
    const host = document.createElement("div")
    document.body.appendChild(host)
    root = createRoot(host)
    await act(async () => root?.render(<EditorToolbar isDark compact portalFormattingMenu />))
    const details = host.querySelector("details")!
    const summary = details.querySelector("summary")!
    await act(async () => { details.open = true; details.dispatchEvent(new Event("toggle")) })
    expect(document.querySelector('[aria-label="Additional formatting controls"]')).not.toBeNull()
    expect(host.querySelector('[aria-label="Additional formatting controls"]')).toBeNull()
    await act(async () => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })))
    expect(details.open).toBe(false)
    expect(document.querySelector('[aria-label="Additional formatting controls"]')).toBeNull()
    expect(document.activeElement).toBe(summary)
  })

  it("loads another document without reporting programmatic content as a user edit", () => {
    const host = document.createElement("div")
    document.body.appendChild(host)
    root = createRoot(host)
    const onChange = vi.fn()
    act(() => root?.render(<RichTextEditor html="<p>First</p>" onChange={onChange} ariaLabel="Scene text" />))
    act(() => root?.render(<RichTextEditor html="<p>Second</p>" onChange={onChange} ariaLabel="Scene text" />))
    expect(state.editor.commands.setContent).toHaveBeenCalledWith("<p>Second</p>", { emitUpdate: false })
    expect(onChange).not.toHaveBeenCalled()
    expect(state.config!.editorProps.attributes).toMatchObject({ role: "textbox", "aria-label": "Scene text", "aria-multiline": "true" })
    state.config!.onUpdate({ editor: { getHTML: () => "<p>Edited</p>", getText: () => "Edited" } })
    expect(onChange).toHaveBeenCalledWith("<p>Edited</p>", "Edited")
  })
})
