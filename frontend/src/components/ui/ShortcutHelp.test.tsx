// @vitest-environment jsdom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ShortcutHelp, SUPPORT_HELP_EVENT } from "./ShortcutHelp"

const askMock = vi.hoisted(() => vi.fn())
const configMock = vi.hoisted(() => vi.fn())
const createIncidentMock = vi.hoisted(() => vi.fn())
const guidesMock = vi.hoisted(() => vi.fn())
const dismissGuidanceMock = vi.hoisted(() => vi.fn())
const restartGuidanceMock = vi.hoisted(() => vi.fn())

const pathnameMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({
  usePathname: pathnameMock,
}))

vi.mock("@/lib/api/support", () => ({
  supportApi: {
    ask: askMock,
    config: configMock,
    createIncident: createIncidentMock,
    guides: guidesMock,
  },
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: { user: { tier: string } }) => unknown) => selector({ user: { tier: "author" } }),
}))

vi.mock("@/lib/stores/uiPreferencesStore", () => ({
  useUiPreferencesStore: (selector: (state: { dismissGuidance: typeof dismissGuidanceMock; restartGuidance: typeof restartGuidanceMock }) => unknown) =>
    selector({ dismissGuidance: dismissGuidanceMock, restartGuidance: restartGuidanceMock }),
}))

let container: HTMLDivElement | null = null
let root: Root | null = null

function renderShortcutHelp() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(<ShortcutHelp />)
  })
}

async function flush() {
  await act(async () => {
    await Promise.resolve()
  })
}

describe("ShortcutHelp support assistant", () => {
  beforeEach(() => {
    pathnameMock.mockReturnValue("/book-1/chapters")
    configMock.mockResolvedValue({
      assistant_enabled: true,
      community_url: "https://discord.gg/mjuWtTWSh",
      corpus_version: "support-v1",
    })
    guidesMock.mockResolvedValue([
      {
        slug: "saving-a-chapter",
        title: "Save or recover a chapter",
        summary: "How to retry a chapter save safely.",
        routes: ["/:bookId/manuscript"],
        workspace: "author",
      },
    ])
    askMock.mockResolvedValue({
      answer: "Your draft stays local until LoreVia confirms the save. Retry from the manuscript editor.",
      sources: [{ slug: "saving-a-chapter", title: "Save or recover a chapter", summary: "Retry safely.", url: "/support/saving-a-chapter" }],
      actions: [{ label: "Open manuscript", href: "/book-1/manuscript", external: false }],
      confidence: 0.9,
      escalation_available: true,
      declined: false,
    })
    createIncidentMock.mockResolvedValue({ reference: "LV-12345678" })
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    container?.remove()
    document.body.innerHTML = ""
    container = null
    root = null
    vi.clearAllMocks()
  })

  it("opens manuscript help from the editor menu without a floating launcher", async () => {
    pathnameMock.mockReturnValue("/book-1/manuscript")
    renderShortcutHelp()
    expect(document.body.querySelector('button[aria-label="Help"]')).toBeNull()
    await act(async () => {
      window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))
      await Promise.resolve()
    })
    await flush()
    expect(document.body.textContent).toContain("LoreVia Support")
  })

  it("answers product-support questions from the support corpus without manuscript text", async () => {
    renderShortcutHelp()

    const helpButton = document.body.querySelector('button[aria-label="Help"]')
    await act(async () => {
      helpButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    await flush()

    const textarea = document.body.querySelector("#lorevia-support-question") as HTMLTextAreaElement | null
    expect(textarea).not.toBeNull()
    await act(async () => {
      const valueSetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set
      valueSetter?.call(textarea, "I pasted a chapter and save did not work")
      textarea!.dispatchEvent(new Event("input", { bubbles: true }))
    })

    const askButton = Array.from(document.body.querySelectorAll("button"))
      .find((button) => button.textContent?.includes("Ask support assistant"))
    await act(async () => {
      askButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    await flush()

    expect(askMock).toHaveBeenCalledWith(
      "I pasted a chapter and save did not work",
      expect.objectContaining({
        route: "/book-1/chapters",
        account_tier: "author",
        device_class: expect.any(String),
      }),
      [],
    )
    expect(JSON.stringify(askMock.mock.calls[0][1])).not.toContain("pasted a chapter")
    expect(document.body.textContent).toContain("Your draft stays local")
    expect(document.body.textContent).toContain("Save or recover a chapter")
    expect(document.body.textContent).toContain("Join Discord")

    await act(async () => {
      const valueSetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set
      valueSetter?.call(textarea, "Where is it?")
      textarea!.dispatchEvent(new Event("input", { bubbles: true }))
    })
    await act(async () => {
      askButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    await flush()

    expect(askMock).toHaveBeenLastCalledWith(
      "Where is it?",
      expect.any(Object),
      [
        { role: "user", content: "I pasted a chapter and save did not work" },
        { role: "assistant", content: "Your draft stays local until LoreVia confirms the save. Retry from the manuscript editor." },
      ],
    )
  })

  it("keeps question-mark typing inside support fields and renders one compact launcher", async () => {
    renderShortcutHelp()

    expect(document.body.querySelectorAll('button[aria-label="Help"]')).toHaveLength(1)
    expect(Array.from(document.body.querySelectorAll("button")).filter((button) => button.textContent?.trim() === "Ask Support")).toHaveLength(0)

    await act(async () => {
      document.body.querySelector('button[aria-label="Help"]')?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    await flush()

    const textarea = document.body.querySelector("#lorevia-support-question") as HTMLTextAreaElement | null
    expect(textarea).not.toBeNull()
    await act(async () => {
      textarea?.focus()
      textarea?.dispatchEvent(new KeyboardEvent("keydown", { key: "?", bubbles: true }))
    })

    expect(document.body.textContent).toContain("LoreVia Support")
    expect(document.body.querySelector("#lorevia-support-question")).toBe(textarea)
    expect(document.body.querySelectorAll('[role="dialog"]')).toHaveLength(1)
  })
})
