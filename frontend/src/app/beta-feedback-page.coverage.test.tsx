// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const replaceMock = vi.hoisted(() => vi.fn())
const pushMock = vi.hoisted(() => vi.fn())
const booksApiMock = vi.hoisted(() => ({ get: vi.fn() }))
const betaReadsApiMock = vi.hoisted(() => ({
  appendQuestions: vi.fn(),
  createAssignment: vi.fn(),
  createFeedbackItem: vi.fn(),
  deleteFeedbackItem: vi.fn(),
  getBookAssignmentDetail: vi.fn(),
  getMineDetail: vi.fn(),
  listBookAssignments: vi.fn(),
  listMine: vi.fn(),
  revokeAssignment: vi.fn(),
  start: vi.fn(),
  submitReview: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}))
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))
vi.mock("next/dynamic", () => ({
  default: () => function AuthorToolsNavStub({ active, title }: { active: string; title: string }) {
    return <aside>{title}:{active}</aside>
  },
}))
vi.mock("@/components/reader/WorkspaceFamilyHeader", () => ({
  WorkspaceFamilyHeader: ({ description, title }: { description: string; title: string }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
}))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/betaReads", () => ({ betaReadsApi: betaReadsApiMock }))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "dark" }) }))

import BetaFeedbackPage from "@/app/(reader)/[bookId]/beta-feedback/page"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null

const assignment = {
  id: "assign-1",
  book_id: "book-1",
  reader_email: "reader@example.com",
  task_label: "First-pass reader response",
  window_days: 7,
  comment_count: 1,
  required_comment_count: 1,
  feedback_item_count: 2,
  required_feedback_item_count: 2,
  progress_pct: 100,
  required_progress_pct: 100,
  status_label: "Active",
  view_bucket: "active",
  state: "active",
  submission_allowed: true,
}
const assignmentDetail = {
  assignment,
  author_questions: [
    { id: "q-1", prompt: "Where did you get confused?", answer_count: 0 },
  ],
  feedback_summary: {
    answer_count: 0,
    confusing_count: 1,
    boring_count: 0,
    favorite_count: 1,
  },
  feedback_items: [
    {
      id: "feedback-1",
      kind: "favorite",
      chapter_number: 2,
      scene_title: "Ash Gate",
      question_prompt: "Where did you get confused?",
      reaction: "favorite",
      anchor_text: "The gate opened.",
      body: "This reveal landed.",
    },
  ],
}

async function renderPage(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  queryClient = client
  await act(async () => {
    root?.render(<QueryClientProvider client={client}>{element}</QueryClientProvider>)
    await Promise.resolve()
  })
}

async function waitForText(expected: string) {
  for (let index = 0; index < 30; index += 1) {
    if ((document.body.textContent ?? "").includes(expected)) return
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
  }
  throw new Error(`Expected text not found: ${expected}. Saw: ${document.body.textContent}`)
}

function text() {
  return document.body.textContent ?? ""
}

function button(label: string, index = 0) {
  const matches = Array.from(document.body.querySelectorAll("button")).filter((item) =>
    item.textContent?.includes(label)
  )
  const match = matches[index]
  if (!match) throw new Error(`Missing button: ${label}`)
  return match
}

async function click(label: string, index = 0) {
  await act(async () => {
    button(label, index).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
    await Promise.resolve()
  })
}

function setFieldValue(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLInputElement
        ? HTMLInputElement.prototype
        : HTMLSelectElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

beforeEach(() => {
  vi.spyOn(window, "confirm").mockReturnValue(true)
  booksApiMock.get.mockResolvedValue({
    id: "book-1",
    title: "The Ember Gate",
    workspace_shell: "author",
    access_class: "owner",
    mode: "author",
    collaboration_permissions: { can_comment: true, can_edit_manuscript: true },
  })
  betaReadsApiMock.listBookAssignments.mockResolvedValue([assignment])
  betaReadsApiMock.listMine.mockResolvedValue([assignment])
  betaReadsApiMock.getBookAssignmentDetail.mockResolvedValue(assignmentDetail)
  betaReadsApiMock.getMineDetail.mockResolvedValue(assignmentDetail)
  betaReadsApiMock.createAssignment.mockResolvedValue({ ...assignment, id: "assign-2" })
  betaReadsApiMock.appendQuestions.mockResolvedValue(assignmentDetail.author_questions)
  betaReadsApiMock.revokeAssignment.mockResolvedValue({ ...assignment, state: "revoked", view_bucket: "completed" })
  betaReadsApiMock.start.mockResolvedValue({ ...assignment, state: "in_progress" })
  betaReadsApiMock.createFeedbackItem.mockResolvedValue(assignmentDetail)
  betaReadsApiMock.deleteFeedbackItem.mockResolvedValue(assignmentDetail)
  betaReadsApiMock.submitReview.mockResolvedValue({ ...assignment, state: "submitted" })
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
  queryClient?.clear()
  queryClient = null
  document.body.innerHTML = ""
  vi.clearAllMocks()
})

describe("BetaFeedbackPage", () => {
  it("keeps confirmed questions when an older detail refresh completes after saving", async () => {
    await renderPage(<BetaFeedbackPage />)
    await waitForText("Assignments")
    await click("reader@example.com")
    await waitForText("Selected assignment")
    let resolveRefresh!: (value: typeof assignmentDetail) => void
    betaReadsApiMock.getBookAssignmentDetail.mockImplementationOnce(() => new Promise((resolve) => { resolveRefresh = resolve }))
    await act(async () => {
      void queryClient?.refetchQueries({ queryKey: ["beta-feedback:book-1:author-detail:assign-1"] })
      await Promise.resolve()
    })
    betaReadsApiMock.appendQuestions.mockResolvedValueOnce([...assignmentDetail.author_questions, { id: "q-new", prompt: "Why the signal?", answer_count: 0 }])
    await act(async () => {
      setFieldValue(container!.querySelector('textarea[aria-label="Additional author questions"]')!, "Why the signal?")
      await Promise.resolve()
    })
    await click("Add questions")
    await waitForText("Questions added.")
    await act(async () => { resolveRefresh(assignmentDetail); await Promise.resolve() })
    expect(text()).toContain("Why the signal?")
  })

  it("drives author assignment creation, question append, navigation, and revoke actions", async () => {
    await renderPage(<BetaFeedbackPage />)
    await waitForText("Assignments")

    expect(text()).toContain("Beta feedback")
    expect(text()).toContain("reader@example.com")
    expect(text()).not.toContain("Selected assignment")
    expect(betaReadsApiMock.listMine).not.toHaveBeenCalled()
    await click("reader@example.com")
    await waitForText("Selected assignment")
    expect(text()).toContain("Responses")

    const extraQuestions = container?.querySelector('textarea[aria-label="Additional author questions"]') as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(extraQuestions, "Which scene dragged?")
      await Promise.resolve()
    })
    await click("Add questions")
    expect(betaReadsApiMock.appendQuestions).toHaveBeenCalledWith("book-1", "assign-1", ["Which scene dragged?"])
    await click("Revoke")
    expect(betaReadsApiMock.revokeAssignment).toHaveBeenCalledWith("book-1", "assign-1")

    await click("New assignment")
    await waitForText("Create beta read")
    const readerEmail = container?.querySelector('input[aria-label="Reader email"]') as HTMLInputElement
    await act(async () => {
      setFieldValue(readerEmail, "new-reader@example.com")
      await Promise.resolve()
    })
    await click("Create beta read")
    expect(betaReadsApiMock.createAssignment).toHaveBeenCalledWith("book-1", expect.objectContaining({
      readerEmail: "new-reader@example.com",
      scopeKind: "full_book",
      chapterStart: null,
      chapterEnd: null,
    }))
    expect(text()).toContain("Beta read assignment created.")
  })

  it("drives reader feedback, requirement modal, removal, start, and final review submission", async () => {
    booksApiMock.get.mockResolvedValueOnce({
      id: "book-1",
      title: "The Ember Gate",
      workspace_shell: "reader",
      access_class: "reader_collaborator",
      mode: "reader",
      collaboration_permissions: { can_comment: true, can_edit_manuscript: false },
    })

    await renderPage(<BetaFeedbackPage />)
    await waitForText("Your beta read")

    expect(text()).toContain("This reveal landed.")
    await click("Start")
    expect(betaReadsApiMock.start).toHaveBeenCalledWith("assign-1")

    const kindSelect = Array.from(container?.querySelectorAll("select") ?? [])[0] as HTMLSelectElement
    const questionSelect = container?.querySelector('select[aria-label="Linked author question"]') as HTMLSelectElement
    const feedbackChapter = container?.querySelector('input[aria-label="Feedback chapter number"]') as HTMLInputElement
    const reaction = container?.querySelector('input[aria-label="Reaction label"]') as HTMLInputElement
    const anchor = container?.querySelector('input[aria-label="Anchor text"]') as HTMLInputElement
    const body = container?.querySelector('textarea[aria-label="Feedback body"]') as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(kindSelect, "answer")
      setFieldValue(questionSelect, "q-1")
      setFieldValue(feedbackChapter, "3")
      setFieldValue(reaction, "favorite")
      setFieldValue(anchor, "The ash key hummed.")
      setFieldValue(body, "I understood the setup here.")
      await Promise.resolve()
    })
    await click("Save feedback item")
    expect(betaReadsApiMock.createFeedbackItem).toHaveBeenCalledWith("assign-1", expect.objectContaining({
      kind: "answer",
      chapterNumber: 3,
      questionId: "q-1",
      anchorText: "The ash key hummed.",
    }))
    expect(text()).toContain("Feedback saved")


    await click("Remove")
    expect(betaReadsApiMock.deleteFeedbackItem).toHaveBeenCalledWith("assign-1", "feedback-1")

    const finalReview = container?.querySelector('textarea[aria-label="Final review"]') as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(finalReview, "The ending worked well.")
      await Promise.resolve()
    })
    await click("Submit review")
    expect(text()).toContain("Complete these before submitting")
    expect(betaReadsApiMock.submitReview).not.toHaveBeenCalled()
  })
})
