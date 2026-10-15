// @vitest-environment jsdom
import { act, useState } from "react"
import { createRoot, type Root } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, describe, expect, it, vi } from "vitest"
import { RevisionMilestonesPanel, type RevisionComparisonView } from "./RevisionMilestonesPanel"

const api = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), compare: vi.fn() }))
vi.mock("@/lib/api/books", () => ({ booksApi: { listRevisionRounds: api.list, createRevisionRound: api.create, compareRevisionRound: api.compare } }))
;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root | undefined
let host: HTMLDivElement
let client: QueryClient
afterEach(() => { act(() => root?.unmount()); host?.remove(); client?.clear(); vi.resetAllMocks() })

async function flush() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) }) }
async function mount() {
  host = document.createElement("div"); document.body.append(host); root = createRoot(host)
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  function Harness() {
    const [label, setLabel] = useState("My revision"); const [busy, setBusy] = useState(false); const [comparison, setComparison] = useState<RevisionComparisonView | null>(null)
    return <RevisionMilestonesPanel bookId="book-1" label={label} onLabelChange={setLabel} busy={busy} onBusyChange={setBusy} comparison={comparison} onComparisonChange={setComparison} />
  }
  await act(async () => root?.render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>)); await flush()
}
async function click(text: string) { const button = [...host.querySelectorAll("button")].find((item) => item.textContent === text); expect(button).toBeTruthy(); await act(async () => button?.click()); await flush() }
const round = { id: "round-1", label: "First pass", created_at: "2026-10-11T10:00:00Z", chapters: [], summary: { word_count: 100, open_finding_count: 1 } }

describe("revision snapshots", () => {
  it("distinguishes failed loading from an empty snapshot list and retries", async () => {
    api.list.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([round])
    await mount()
    expect(host.textContent).toContain("Snapshots could not be loaded")
    expect(host.textContent).not.toContain("No snapshots captured")
    await click("Refresh snapshots")
    expect(host.textContent).toContain("First pass")
  })

  it("retains a failed capture label and inserts the confirmed snapshot on retry", async () => {
    api.list.mockResolvedValue([]); api.create.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ ...round, label: "My revision" })
    await mount(); await click("Capture round")
    expect(host.querySelector("input")?.value).toBe("My revision")
    expect(host.textContent).toContain("Your label is retained")
    await click("Capture round")
    expect(host.querySelector("input")?.value).toBe("")
    expect(host.textContent).toContain("Captured My revision.")
  })

  it("keeps full comparison evidence after a later comparison fails", async () => {
    api.list.mockResolvedValue([round])
    api.compare.mockResolvedValueOnce({ base_round_id: "round-1", changed_chapters: [2], added_chapters: [4], removed_chapters: [1], word_count_delta: -10, scene_count_delta: -1, open_finding_delta: -1, open_beta_feedback_delta: 0 }).mockRejectedValueOnce(new Error("offline"))
    await mount(); await click("Compare now")
    expect(host.textContent).toContain("Removed chapters: 1")
    expect(host.textContent).toContain("Compared with First pass")
    await click("Compare now")
    expect(host.textContent).toContain("previous comparison is retained")
    expect(host.textContent).toContain("Changed chapters: 2")
  })
})
