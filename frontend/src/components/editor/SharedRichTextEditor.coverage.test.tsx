// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const commandCalls = vi.hoisted(() => [] as string[])
const editorState = vi.hoisted(() => ({
  html: "<p>Initial</p>",
  text: "Initial",
  setContent: vi.fn(),
}))
const promptMock = vi.hoisted(() => vi.fn())

function makeChain() {
  const chain: Record<string, (...args: unknown[]) => typeof chain | boolean> = {}
  const chainMethods = [
    "focus",
    "setImage",
    "setFontFamily",
    "setFontSize",
    "toggleHeading",
    "toggleBold",
    "toggleItalic",
    "toggleUnderline",
    "toggleStrike",
    "toggleBulletList",
    "toggleOrderedList",
    "setTextAlign",
    "extendMarkRange",
    "setLink",
    "insertContent",
    "undo",
    "redo",
    "setColor",
    "toggleHighlight",
    "setLineHeight",
    "setParagraphSpacing",
    "unsetAllMarks",
    "clearNodes",
    "toggleTaskList",
    "toggleBlockquote",
    "setHorizontalRule",
    "setFirstLineIndent",
  ]
  chainMethods.forEach((method) => {
    chain[method] = (...args: unknown[]) => {
      commandCalls.push(`${method}:${JSON.stringify(args)}`)
      return chain
    }
  })
  chain.run = () => {
    commandCalls.push("run")
    return true
  }
  return chain
}

const fakeEditor = vi.hoisted(() => ({
  chain: vi.fn(makeChain),
  commands: {
    setContent: vi.fn((html: string) => {
      editorState.setContent(html)
    }),
  },
  getHTML: vi.fn(() => editorState.html),
  getText: vi.fn(() => editorState.text),
}))

vi.mock("@tiptap/react", () => ({
  EditorContent: ({ editor }: { editor: unknown }) => <div data-testid="editor-content">{editor ? "Editor mounted" : "No editor"}</div>,
  useEditor: vi.fn((options: { onUpdate?: (payload: { editor: typeof fakeEditor }) => void }) => {
    options.onUpdate?.({ editor: fakeEditor })
    return fakeEditor
  }),
}))
vi.mock("@tiptap/core", () => ({
  Extension: { create: (config: Record<string, unknown>) => config },
  Mark: { create: (config: Record<string, unknown>) => config },
  Node: { create: (config: Record<string, unknown>) => config },
  mergeAttributes: (...values: Record<string, unknown>[]) => Object.assign({}, ...values),
}))
vi.mock("@tiptap/starter-kit", () => ({ default: { configure: vi.fn((options) => ({ name: "starter", options })) } }))
vi.mock("@tiptap/extension-underline", () => ({ default: { name: "underline" } }))
vi.mock("@tiptap/extension-text-align", () => ({ default: { configure: vi.fn((options) => ({ name: "textAlign", options })) } }))
vi.mock("@tiptap/extension-link", () => ({ default: { configure: vi.fn((options) => ({ name: "link", options })) } }))
vi.mock("@tiptap/extension-image", () => ({ default: { name: "image" } }))
vi.mock("@tiptap/extension-highlight", () => ({ default: { configure: vi.fn((options) => ({ name: "highlight", options })) } }))
vi.mock("@tiptap/extension-text-style", () => ({ TextStyle: { name: "textStyle" } }))
vi.mock("@tiptap/extension-color", () => ({ default: { name: "color" } }))
vi.mock("@tiptap/extension-task-list", () => ({ default: { name: "taskList" } }))
vi.mock("@tiptap/extension-task-item", () => ({ default: { configure: vi.fn((options) => ({ name: "taskItem", options })) } }))
vi.mock("@/components/ui/Tooltip", () => ({
  Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>,
}))
vi.mock("@/components/ui/PromptDialog", () => ({ usePromptDialog: () => promptMock }))

import { EditorToolbar, RichTextEditor } from "@/components/editor/SharedRichTextEditor"

let root: Root | null = null
let container: HTMLDivElement | null = null

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
    await new Promise((resolve) => window.setTimeout(resolve, 0))
  })
}

async function click(label: string, index = 0) {
  const matches = Array.from(container?.querySelectorAll("button") ?? []).filter((button) => button.textContent?.includes(label) || button.getAttribute("aria-label")?.includes(label))
  const target = matches[index]
  if (!target) throw new Error(`Missing button: ${label}`)
  await act(async () => {
    target.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

function changeSelect(label: string, value: string) {
  const select = Array.from(container?.querySelectorAll("select") ?? []).find((item) => item.getAttribute("aria-label") === label)
  if (!select) throw new Error(`Missing select: ${label}`)
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set
  setter?.call(select, value)
  select.dispatchEvent(new Event("change", { bubbles: true }))
}

beforeEach(() => {
  commandCalls.length = 0
  fakeEditor.chain.mockClear()
  fakeEditor.commands.setContent.mockClear()
  fakeEditor.getHTML.mockClear()
  fakeEditor.getText.mockClear()
  editorState.html = "<p>Initial</p>"
  editorState.text = "Initial"
  editorState.setContent.mockClear()
  promptMock.mockResolvedValue("https://example.com")
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
})

describe("SharedRichTextEditor runtime coverage", () => {
  it("registers an editor and drives toolbar commands, mentions, dropdown controls, and content updates", async () => {
    const onChange = vi.fn()
    await renderElement(
      <div>
        <RichTextEditor
          html="<p>Initial</p>"
          onChange={onChange}
          editorKey="draft"
          className="outer"
          contentClassName="inner"
        />
        <EditorToolbar
          isDark
          compact
          editorKey="draft"
          characters={[{ id: "char-1", name: "Mara" } as never]}
          onAddComment={() => commandCalls.push("comment")}
          onOpenNotes={() => commandCalls.push("notes")}
        />
      </div>
    )

    expect(container?.textContent).toContain("Editor mounted")
    expect(onChange).toHaveBeenCalledWith("<p>Initial</p>", "Initial")
    await click("@")
    changeSelect("Font family", "Georgia")
    changeSelect("Font size", "16")
    await click("Bold")
    await click("Italic")
    await click("Heading 2")
    await click("Insert link")
    await click("@Mara")
    await click("Comment")
    await click("Notes")
    changeSelect("Text color", "#1d4ed8")
    changeSelect("Highlight color", "#bfdbfe")
    changeSelect("Line height", "2")
    changeSelect("Paragraph spacing", "0.4rem")
    await click("Clear")
    await click("Checklist")
    await click("Scene break")
    await click("Page break")
    await click("Indent")

    expect(commandCalls.join(" ")).toContain("toggleBold")
    expect(commandCalls.join(" ")).toContain("setLink")
    expect(commandCalls.join(" ")).toContain("insertContent")
    expect(commandCalls).toContain("comment")
    expect(commandCalls).toContain("notes")

    await act(async () => {
      root?.render(
        <RichTextEditor
          html="<p>Updated</p>"
          onChange={onChange}
          editorKey="draft"
        />
      )
      await Promise.resolve()
    })
    expect(editorState.setContent).toHaveBeenCalledWith("<p>Updated</p>")
  })
})
