// @vitest-environment jsdom
import { act } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useAuthorLoopActions } from "./authorLoopPage.actions"
import { deadlineFromWindow } from "@/lib/utils/authorLoop"
import type { WriterWorkspace } from "@/types/book"
import type { BetaReadAssignmentDetail, BetaReadFeedbackItem } from "@/types/betaRead"

const api = vi.hoisted(() => ({ update: vi.fn(), invite: vi.fn(), feedback: vi.fn(), link: vi.fn() }))
vi.mock("@/lib/api/books", () => ({ booksApi: { updateWriterWorkspace: api.update } }))
vi.mock("@/lib/api/betaReads", () => ({ betaReadsApi: { createAssignment: api.invite, updateBookFeedbackItem: api.feedback, getGuestLink: api.link } }))
;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const cleanups: (() => void)[] = []
afterEach(() => { cleanups.splice(0).forEach((cleanup) => cleanup()); vi.resetAllMocks(); vi.restoreAllMocks() })

function mount(overrides: Partial<Parameters<typeof useAuthorLoopActions>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const workspace = { revision_board: { items: [] }, goal_calendar: [] } as unknown as WriterWorkspace
  client.setQueryData(["book:book-1:writer-workspace"], workspace)
  api.update.mockImplementation(async (_book: string, patch: Partial<WriterWorkspace>) => ({ ...client.getQueryData<WriterWorkspace>(["book:book-1:writer-workspace"]), ...patch }))
  const args = {
    bookId: "book-1", totalChapters: 3, writerWorkspace: workspace,
    issueCards: [{ id: "issue-1", title: "Clarify the gate", severity: "high", affected: [], citation: "Chapter 1", explanation: "The opening rule changes.", suggestedFix: "State the exception.", confidence: "", status: "pending", sourceLabel: "report" }] as Parameters<typeof useAuthorLoopActions>[0]["issueCards"],
    selectedAssignment: { assignment: { id: "assignment-1" }, feedback_items: [] } as unknown as BetaReadAssignmentDetail,
    draft: { readerEmail: "reader@example.com", scopeKind: "chapter_range", chapterStart: "1", chapterEnd: "3", deadline: deadlineFromWindow(7), authorQuestions: "What was unclear?" },
    setReaderEmail: vi.fn(), setSelectedAssignmentId: vi.fn(), setStatusMessage: vi.fn(), ...overrides,
  }
  let actions!: ReturnType<typeof useAuthorLoopActions>
  function Harness() { actions = useAuthorLoopActions(args); return null }
  const container = document.createElement("div"); document.body.append(container)
  const root = createRoot(container)
  act(() => root.render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>))
  cleanups.push(() => { act(() => root.unmount()); client.clear(); container.remove() })
  return { client, args, current: () => actions }
}

describe("revision workflow actions", () => {
  it("restores an existing task decision when undoing a dismissal", async () => {
    const view = mount()
    await act(async () => { await view.current().handleIssueStatus("issue-1", "task_created") })
    await act(async () => { await view.current().handleIssueStatus("issue-1", "ignored") })
    await act(async () => { await view.current().handleIssueStatus("issue-1", "pending") })
    const saved = view.client.getQueryData<WriterWorkspace>(["book:book-1:writer-workspace"])!
    expect(saved.revision_board.items[0].status).toBe("task_created")
    expect(saved.goal_calendar).toHaveLength(1)
  })
  it("blocks overlapping decisions and merges the latest confirmed task list", async () => {
    const view = mount()
    let finish!: (value: unknown) => void
    api.update.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    let pending!: Promise<void>
    act(() => { pending = view.current().handleIssueStatus("issue-1", "task_created") })
    await act(async () => { await view.current().handleIssueStatus("issue-1", "ignored") })
    expect(api.update).toHaveBeenCalledTimes(1)
    await act(async () => { finish(api.update.mock.calls[0][1]); await pending })
    await act(async () => { await view.current().handleIssueStatus("issue-1", "task_created") })
    expect(api.update.mock.calls[1][1].goal_calendar).toHaveLength(1)
  })

  it("retains invitations after failed requests and rejects invalid chapter ranges", async () => {
    const view = mount(); api.invite.mockRejectedValueOnce(new Error("offline"))
    await act(async () => { await view.current().handleCreateAssignment() })
    expect(view.args.setReaderEmail).not.toHaveBeenCalled()
    expect(view.args.setStatusMessage).toHaveBeenLastCalledWith(expect.stringContaining("draft is retained"))
    view.args.draft.chapterStart = "1.5"
    await act(async () => { await view.current().handleCreateAssignment() })
    expect(api.invite).toHaveBeenCalledTimes(1)
    expect(view.args.setStatusMessage).toHaveBeenLastCalledWith(expect.stringContaining("whole chapter numbers"))
  })

  it("uses the returned invitation instead of a stale readback", async () => {
    const view = mount(); api.invite.mockResolvedValueOnce({ id: "new-assignment", reader_email: "reader@example.com" })
    await act(async () => { await view.current().handleCreateAssignment() })
    expect(view.client.getQueryData(["author-loop:book-1:beta-assignments"])).toEqual([{ id: "new-assignment", reader_email: "reader@example.com" }])
    expect(view.args.setReaderEmail).toHaveBeenCalledWith("")
    expect(view.args.setSelectedAssignmentId).toHaveBeenCalledWith("new-assignment")
  })

  it("retries partial feedback saves without duplicating tasks and links the actual task id", async () => {
    const view = mount()
    const feedback = { id: "feedback-1", body: "Clarify the gate rule", chapter_number: 2, author_status: "open" } as BetaReadFeedbackItem
    api.feedback.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ assignment: { id: "assignment-1" }, feedback_items: [{ ...feedback, author_status: "task_created" }] })
    await act(async () => { await view.current().handleFeedbackStatus(feedback, "task_created") })
    expect(view.args.setStatusMessage).toHaveBeenLastCalledWith(expect.stringContaining("task was saved"))
    await act(async () => { await view.current().handleFeedbackStatus(feedback, "task_created") })
    expect(api.update).toHaveBeenCalledTimes(1)
    expect(api.feedback).toHaveBeenLastCalledWith("book-1", "assignment-1", "feedback-1", { authorStatus: "task_created", authorTaskId: "revision-task:beta-feedback:feedback-1" })
    expect(view.client.getQueryData<BetaReadAssignmentDetail>(["author-loop:book-1:beta-detail:assignment-1"])?.feedback_items[0].author_status).toBe("task_created")
  })

  it("keeps a generated private link available after clipboard failure", async () => {
    const view = mount()
    api.link.mockResolvedValueOnce({ share_url: "https://example.test/review/private" })
    // jsdom omits the clipboard API; this follows the same manual-copy recovery path.
    await act(async () => { await view.current().handleCopyGuestLink() })
    expect(view.current().guestLink).toEqual({ assignmentId: "assignment-1", url: "https://example.test/review/private" })
    expect(view.args.setStatusMessage).toHaveBeenLastCalledWith(expect.stringContaining("select and copy"))
  })
})
