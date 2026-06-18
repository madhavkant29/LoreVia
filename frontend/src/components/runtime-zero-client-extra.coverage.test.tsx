// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const authState = vi.hoisted(() => ({
  hydrated: true,
  user: { id: "user-1" } as { id: string } | null,
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/dynamic", () => ({
  default: () => function DynamicRuntime() {
    return <div>Dynamic runtime</div>
  },
}))

vi.mock("@/components/auth/AuthBootstrap", () => ({ AuthBootstrap: () => <div>Auth bootstrap</div> }))
vi.mock("@/components/app/QueryProvider", () => ({ QueryProvider: ({ children }: { children: ReactNode }) => <>{children}</> }))
vi.mock("@/components/app/UxRuntimeProvider", () => ({ UxRuntimeProvider: ({ children }: { children: ReactNode }) => <>{children}</> }))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "dark" }) }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector?: (state: typeof authState) => unknown) => typeof selector === "function" ? selector(authState) : authState,
}))

import { AppRuntime } from "@/components/app/AppRuntime"
import { PWARegister } from "@/components/app/PWARegister"
import { EventModal } from "@/components/reader/EventModal"
import { FolderTree } from "@/components/reader/FolderTree"
import { RecallCard } from "@/components/intelligence/RecallCard"
import { FirstTimeTooltip } from "@/components/tooltips/FirstTimeTooltip"
import { ReadingProgressRail } from "@/components/reader/ReadingProgressRail"
import { CharacterWorkspaceHeader } from "@/components/reader/CharacterWorkspaceHeader"
import { ShortcutHelp } from "@/components/ui/ShortcutHelp"
import { NotificationBellShell } from "@/components/layout/NotificationBellShell"
import { StatusNavigation } from "@/components/status/StatusNavigation"

let root: Root | null = null
let container: HTMLDivElement | null = null
const localStore: Record<string, string> = {}
const localStorageMock = {
  get length() { return Object.keys(localStore).length },
  clear: vi.fn(() => Object.keys(localStore).forEach((key) => delete localStore[key])),
  getItem: vi.fn((key: string) => localStore[key] ?? null),
  key: vi.fn((index: number) => Object.keys(localStore)[index] ?? null),
  removeItem: vi.fn((key: string) => { delete localStore[key] }),
  setItem: vi.fn((key: string, value: string) => { localStore[key] = value }),
}

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  authState.hydrated = true
  authState.user = { id: "user-1" }
  Object.defineProperty(window, "localStorage", { configurable: true, value: localStorageMock })
  window.localStorage.clear()
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  document.body.innerHTML = ""
  root = null
  container = null
  vi.unstubAllEnvs()
})

describe("zero-coverage client runtime components", () => {
  it("renders story and character event details and closes the modal", async () => {
    const onClose = vi.fn()
    await renderElement(
      <EventModal
        isDark
        onClose={onClose}
        event={{
          kind: "story",
          chapter_number: 3,
          chapter_title: "The Gate",
          event_title: "Gate opens",
          description: "Mara turns the key.",
          importance: 9,
          event_type: "plot_turn",
          involved_character_names: ["Mara", "Theo"],
        } as never}
      />,
    )
    expect(container?.textContent).toContain("Story major event")
    expect(container?.textContent).toContain("plot turn")
    expect(container?.textContent).toContain("Theo")
    await clickButton("Close")
    expect(onClose).toHaveBeenCalled()

    cleanupRenderedTree()
    await renderElement(
      <EventModal
        isDark={false}
        onClose={onClose}
        event={{
          kind: "character",
          chapter_number: 4,
          character_name: "Mara",
          event_title: "Chooses trust",
          description: "Mara trusts Theo.",
          impact_score: 8,
          growth_direction: "positive",
          growth_magnitude: 7,
          role: "protagonist",
          accomplishments: ["Opened the gate"],
        } as never}
      />,
    )
    expect(container?.textContent).toContain("Mara major event")
    expect(container?.textContent).toContain("Opened the gate")
  })

  it("builds nested note folders and selects files", async () => {
    const onToggleFolder = vi.fn()
    const onSelect = vi.fn()
    await renderElement(
      <FolderTree
        paths={["Characters/Mara.md", "Characters/Theo.md", "World/Gate.md"]}
        activePath="Characters/Mara.md"
        collapsed={{ World: true }}
        onToggleFolder={onToggleFolder}
        onSelect={onSelect}
        isDark
      />,
    )

    expect(container?.textContent).toContain("Characters")
    expect(container?.textContent).toContain("Mara")
    expect(container?.textContent).not.toContain("Gate")
    await clickButton("World")
    await clickButton("Mara")
    expect(onToggleFolder).toHaveBeenCalledWith("World")
    expect(onSelect).toHaveBeenCalledWith("Characters/Mara.md")
  })

  it("renders recall and reading progress controls", async () => {
    const onDismiss = vi.fn()
    const onContinue = vi.fn()
    await renderElement(
      <>
        <RecallCard recall="Mara found the brass key." lastChapter={5} onDismiss={onDismiss} onContinue={onContinue} />
        <ReadingProgressRail theme="dark" progressPercent={125} wordsRead={1200} totalWords={2400} />
      </>,
    )

    expect(container?.textContent).toContain("grounded recap through chapter 5")
    expect(container?.textContent).toContain("125%")
    expect(container?.textContent).toContain("1,200")
    await clickButton("Continue Reading")
    await clickButton("Dismiss")
    expect(onContinue).toHaveBeenCalled()
    expect(onDismiss).toHaveBeenCalled()
    const fill = Array.from(container?.querySelectorAll<HTMLElement>("div") ?? []).find((node) => node.style.height === "100%")
    expect(fill).toBeTruthy()
  })

  it("shows first-time help once and persists its dismissal", async () => {
    const onDismiss = vi.fn()
    await renderElement(<FirstTimeTooltip storageKey="tip:reader" title="Reader tools" message="Use the rail." isDark onDismiss={onDismiss} />)
    await flushAsync()
    expect(container?.textContent).toContain("Reader tools")
    await clickButton("Got it")
    expect(window.localStorage.getItem("tip:reader")).toBe("true")
    expect(onDismiss).toHaveBeenCalled()
    expect(container?.textContent).not.toContain("Reader tools")
  })

  it("renders the character workspace header and shell navigation", async () => {
    const onBack = vi.fn()
    await renderElement(
      <>
        <CharacterWorkspaceHeader
          title="Character Bible"
          description="Review the cast."
          stats={<span>12 profiles</span>}
          actions={<button type="button">Add character</button>}
          onBack={onBack}
          isDark
        />
        <NotificationBellShell />
        <StatusNavigation />
      </>,
    )

    expect(container?.textContent).toContain("12 profiles")
    expect(container?.textContent).toContain("Go to library")
    expect(container?.querySelector('a[aria-label="Open notifications"]')?.getAttribute("href")).toBe("/notifications")
    await clickButton("Projects")
    expect(onBack).toHaveBeenCalled()

    cleanupRenderedTree()
    authState.user = null
    await renderElement(<StatusNavigation />)
    expect(container?.textContent).toContain("Sign in or create account")
  })

  it("toggles shortcut help from the keyboard and records dismissal", async () => {
    await renderElement(<ShortcutHelp />)
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "?" }))
      await Promise.resolve()
    })
    expect(container?.textContent).toContain("Shortcuts")
    await clickButton("Dismiss")
    expect(window.localStorage.getItem("lorevia-shortcut-help-dismissed:v1")).toBe("true")

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "?" }))
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }))
      await Promise.resolve()
    })
    expect(container?.textContent).not.toContain("Press ? anytime")
  })

  it("mounts the app runtime providers and dynamic browser-only services", async () => {
    await renderElement(<AppRuntime><main>Application body</main></AppRuntime>)
    expect(container?.textContent).toContain("Auth bootstrap")
    expect(container?.textContent).toContain("Dynamic runtime")
    expect(container?.textContent).toContain("Application body")
  })

  it("unregisters service workers in local development", async () => {
    const unregister = vi.fn().mockResolvedValue(true)
    const getRegistrations = vi.fn().mockResolvedValue([{ unregister }])
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { getRegistrations, register: vi.fn() },
    })

    await renderElement(<PWARegister />)
    await flushAsync()

    expect(getRegistrations).toHaveBeenCalled()
    expect(unregister).toHaveBeenCalled()
  })
})

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

function cleanupRenderedTree() {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  document.body.innerHTML = ""
  root = null
  container = null
}

async function flushAsync() {
  await act(async () => {
    await Promise.resolve()
    await new Promise((resolve) => window.setTimeout(resolve, 0))
  })
}

async function clickButton(text: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) => node.textContent?.includes(text))
  expect(button, `button containing ${text}`).toBeTruthy()
  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}
