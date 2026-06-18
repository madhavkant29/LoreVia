// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const useQueryMock = vi.hoisted(() => vi.fn())
const booksApiMock = vi.hoisted(() => ({
  createCollaborator: vi.fn(),
  get: vi.fn(),
  getCollaboratorActivity: vi.fn(),
  listCollaborators: vi.fn(),
  updateCollaborator: vi.fn(),
}))
const betaReadsApiMock = vi.hoisted(() => ({
  createAssignment: vi.fn(),
  listBookAssignments: vi.fn(),
  revokeAssignment: vi.fn(),
}))

vi.mock("@tanstack/react-query", () => ({ useQuery: useQueryMock }))
vi.mock("next/dynamic", () => ({
  default: () => function MockAuthorToolsNav() {
    return <nav>Author tools nav</nav>
  },
}))
vi.mock("next/navigation", () => ({ useParams: () => ({ bookId: "book-1" }) }))
vi.mock("@/components/reader/WorkspaceFamilyHeader", () => ({
  WorkspaceFamilyHeader: ({ title, description }: { title: string; description: string }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
}))
vi.mock("@/components/ui/Tooltip", () => ({
  Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>,
}))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/betaReads", () => ({ betaReadsApi: betaReadsApiMock }))
vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  bookCacheKey: (...parts: string[]) => parts.join(":"),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "dark" }) }))

import CollaborationPage from "@/app/(reader)/[bookId]/collaboration/page"

let container: HTMLDivElement | null = null
let root: Root | null = null

const bookFixture = {
  id: "book-1",
  title: "Gate Draft",
  workspace_shell: "author",
  mode: "author",
}

const collaboratorFixture = {
  id: "collab-1",
  email: "editor@example.com",
  display_name: "Edda Editor",
  role: "editor",
  invite_status: "active",
  permissions: {
    can_edit_manuscript: true,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: true,
    can_comment: true,
    can_view_selected_chapters_only: false,
  },
  scope: {
    chapter_start: 1,
    chapter_end: 12,
    character_bible: true,
    continuity_report: true,
    reader_confusion_report: true,
  },
}

const betaAssignmentFixture = {
  id: "assignment-1",
  reader_email: "reader@example.com",
  task_label: "Chapters 1-3 response",
  scope_kind: "chapter_range",
  section_label: null,
  chapter_start: 1,
  chapter_end: 3,
  window_days: 5,
  expires_at: "2026-01-08T00:00:00Z",
  required_progress_pct: 80,
  required_comment_count: 2,
  required_feedback_item_count: 3,
  require_final_feedback: true,
  progress_pct: 40,
  submitted_at: null,
  question_count: 2,
  status_label: "In progress",
  view_bucket: "active",
  state: "in_progress",
  penalty_warning: "Due soon.",
}

const activityFixture = {
  items: [
    {
      id: "activity-1",
      kind: "chapter_comment",
      title: "Chapter note",
      body: "The gate sequence needs one clearer beat.",
      chapter_number: 2,
      chapter_title: "The Key",
      created_at: "2026-01-02T00:00:00Z",
    },
    {
      id: "activity-2",
      kind: "annotation",
      title: "Line annotation",
      body: "Strong voice here.",
      chapter_number: null,
      chapter_title: null,
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
  assignments: [betaAssignmentFixture],
  chapter_comment_count: 2,
  annotation_count: 1,
  latest_activity_at: "2026-01-02T00:00:00Z",
}

async function renderPage(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

function setFieldValue(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

async function waitForText(expected: string) {
  for (let index = 0; index < 30; index += 1) {
    if ((container?.textContent ?? "").includes(expected)) return
    await act(flush)
  }
  throw new Error(`Missing text: ${expected}\n${container?.textContent ?? ""}`)
}

function button(label: string, index = 0) {
  const matches = Array.from(container?.querySelectorAll("button") ?? []).filter((item) =>
    item.textContent?.includes(label)
  )
  const match = matches[index]
  if (!match) throw new Error(`Missing button: ${label}`)
  return match
}

async function click(label: string, index = 0) {
  await act(async () => {
    button(label, index).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

beforeEach(() => {
  const refetch = vi.fn().mockResolvedValue({})
  booksApiMock.createCollaborator.mockResolvedValue({})
  booksApiMock.updateCollaborator.mockResolvedValue({})
  betaReadsApiMock.createAssignment.mockResolvedValue({})
  betaReadsApiMock.revokeAssignment.mockResolvedValue({})
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: string }) => {
    if (queryKey === "book-1:detail") return { data: bookFixture, isLoading: false, refetch }
    if (queryKey === "collaboration:book-1:collaborators") return { data: [collaboratorFixture], isLoading: false, refetch }
    if (queryKey === "collaboration:book-1:beta-assignments") return { data: [betaAssignmentFixture], isLoading: false, refetch }
    if (String(queryKey).includes("collaborator-activity") || String(queryKey).includes("all-activity")) {
      return { data: activityFixture, isLoading: false, refetch }
    }
    return { data: null, isLoading: false, refetch }
  })
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
  vi.clearAllMocks()
})

describe("CollaborationPage", () => {
  it("renders collaboration activity and drives share and beta-read actions", async () => {
    await renderPage(<CollaborationPage />)
    await waitForText("Gate Draft collaborators")
    await waitForText("Edda Editor")
    await waitForText("Chapter note")
    await waitForText("Chapters 1-3 response")

    setFieldValue(container?.querySelector("#collaborator-email") as HTMLInputElement, "new@example.com")
    setFieldValue(container?.querySelector("#collaborator-display-name") as HTMLInputElement, "New Reader")
    setFieldValue(container?.querySelector("#collaborator-role") as HTMLSelectElement, "commenter")
    await click("Save share")
    expect(booksApiMock.createCollaborator).toHaveBeenCalledWith("book-1", expect.objectContaining({
      email: "new@example.com",
      displayName: "New Reader",
      role: "commenter",
    }))
    await waitForText("Share saved.")

    await click("View activity")
    await waitForText("Recent activity from Edda Editor.")
    await click("All")
    await waitForText("Activity from all 1 collaborator.")

    await click("Revoke")
    expect(booksApiMock.updateCollaborator).toHaveBeenCalledWith("book-1", "collab-1", { inviteStatus: "revoked" })

    setFieldValue(container?.querySelector("#beta-reader-email") as HTMLInputElement, "beta@example.com")
    setFieldValue(container?.querySelector("#beta-task-label") as HTMLInputElement, "Middle act beta read")
    await click("Section")
    setFieldValue(container?.querySelector("#beta-start-chapter") as HTMLInputElement, "4")
    setFieldValue(container?.querySelector("#beta-end-chapter") as HTMLInputElement, "7")
    setFieldValue(container?.querySelector("#beta-section-label") as HTMLInputElement, "Middle act")
    setFieldValue(container?.querySelector("#beta-author-questions") as HTMLTextAreaElement, "What dragged?\nWhat surprised you?")
    await click("Grant beta read")
    expect(betaReadsApiMock.createAssignment).toHaveBeenCalledWith("book-1", expect.objectContaining({
      readerEmail: "beta@example.com",
      taskLabel: "Middle act beta read",
      scopeKind: "section",
      chapterStart: 4,
      chapterEnd: 7,
      sectionLabel: "Middle act",
      authorQuestions: ["What dragged?", "What surprised you?"],
    }))

    await click("Revoke beta read")
    expect(betaReadsApiMock.revokeAssignment).toHaveBeenCalledWith("book-1", "assignment-1")
  })
})
