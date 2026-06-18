// @vitest-environment jsdom

import React, { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const backMock = vi.hoisted(() => vi.fn())
const captureMock = vi.hoisted(() => vi.fn())
const useQueryMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({ default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a> }))
vi.mock("next/navigation", () => ({ useParams: () => ({ bookId: "book-1" }), useRouter: () => ({ back: backMock }) }))
vi.mock("next/dynamic", () => ({ default: () => (props: Record<string, unknown>) => <div>Worldbuilding dynamic {String(props.bookId)} {String(props.focus)}</div> }))
vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: useQueryMock,
}))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "dark" }) }))
vi.mock("@/lib/analytics/posthog", () => ({ capture: captureMock }))
vi.mock("@/components/intelligence/PlotTracker", () => ({ PlotTracker: ({ bookId, mode }: { bookId: string; mode: string }) => <div>Plot tracker {bookId} {mode}</div> }))
vi.mock("@/components/reader/WorkspaceFamilyHeader", () => ({ WorkspaceFamilyHeader: ({ title, actions }: { title: string; actions?: ReactNode }) => <header>{title}{actions}</header> }))
vi.mock("@/components/ui/Workspace", () => ({
  WorkspacePage: ({ children }: { children: ReactNode }) => <main>{children}</main>,
  WorkspacePanel: ({ children }: { children: ReactNode }) => <section>{children}</section>,
}))

import CompliancePage, { metadata as complianceMetadata } from "./(reader)/[bookId]/compliance/page"
import RelationshipEvolutionPage from "./(reader)/[bookId]/relationship-evolution/page"
import WorldGapPage from "./(reader)/[bookId]/world-gap/page"
import PlotThreadsPage from "./(reader)/[bookId]/plot-threads/page"

let root: Root | null = null
let container: HTMLDivElement | null = null

beforeEach(() => {
  backMock.mockReset()
  captureMock.mockReset()
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: string }) => {
    if (String(queryKey).includes("progress")) return { data: { current_chapter: 4 } }
    return {
      data: {
        pairs: [{
          characters: ["Mara", "Joren"],
          events: [
            { chapter: 2, type: "alliance", description: "They share the key." },
            { chapter: 4, type: "conflict", description: null },
          ],
        }],
      },
    }
  })
})

afterEach(() => {
  if (root) act(() => root?.unmount())
  container?.remove()
  root = null
  container = null
})

describe("reader zero-coverage pages", () => {
  it("renders compliance, world gap, and plot thread workspace wrappers", async () => {
    expect(complianceMetadata.title).toBe("Compliance Notice")
    await render(<CompliancePage />)
    expect(container?.textContent).toContain("Compliance Notice")
    expect(container?.querySelector('a[href^="mailto:"]')).not.toBeNull()

    await rerender(<WorldGapPage />)
    expect(container?.textContent).toContain("Worldbuilding dynamic book-1 gap")
    expect(container?.querySelector('a[href="/book-1/advisor"]')).not.toBeNull()

    await rerender(<PlotThreadsPage />)
    expect(container?.textContent).toContain("Plot tracker book-1 dashboard")
    expect(captureMock).toHaveBeenCalledWith("plot_threads_opened", { book_id: "book-1" })
  })

  it("renders relationship evolution data, chapter updates, back action, and unavailable state", async () => {
    await render(<RelationshipEvolutionPage />)
    await act(async () => { await Promise.resolve() })
    expect(container?.textContent).toContain("Showing relationship events through chapter 4")
    expect(container?.textContent).toContain("Mara")
    expect(container?.textContent).toContain("They share the key.")
    const back = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Back"))
    act(() => back?.click())
    expect(backMock).toHaveBeenCalled()

    useQueryMock.mockImplementation(({ queryKey }: { queryKey: string }) => String(queryKey).includes("progress") ? { data: null } : { data: null })
    await rerender(<RelationshipEvolutionPage />)
    expect(container?.textContent).toContain("Relationship evolution unavailable")
  })
})

async function render(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

async function rerender(element: ReactElement) {
  if (!root) throw new Error("Root not initialized")
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}
