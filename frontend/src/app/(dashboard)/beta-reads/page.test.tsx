// @vitest-environment jsdom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { BetaReadAssignment } from "@/types/reader"
import type { BetaReadAssignmentDetail } from "@/types/betaRead"

const mockPush = vi.fn()
let mockItems: BetaReadAssignment[] = []
let mockDetails: Array<{ data: BetaReadAssignmentDetail | null; isLoading: boolean }> = []

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: mockItems,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useQueries: () => mockDetails,
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock("@/components/ui/Workspace", () => ({
  WorkspacePage: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div>,
  WorkspacePanel: ({ children, className }: { children: ReactNode; className?: string }) => <section className={className}>{children}</section>,
  WorkspaceHeader: ({ title, description, meta }: { title: string; description: string; meta?: ReactNode }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {meta}
    </header>
  ),
  WorkspaceTabButton: ({ children, onClick }: { children: ReactNode; onClick?: () => void }) => <button type="button" onClick={onClick}>{children}</button>,
  WorkspaceEmptyState: ({ title, body }: { title: string; body: string }) => (
    <div>
      <p>{title}</p>
      <p>{body}</p>
    </div>
  ),
}))

vi.mock("@/lib/api/reader", () => ({
  readerApi: {
    listBetaReads: vi.fn(),
    startBetaRead: vi.fn(),
  },
}))

vi.mock("@/lib/api/betaReads", () => ({
  betaReadsApi: {
    getMineDetail: vi.fn(),
  },
}))

vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (key: string) => key,
}))

let container: HTMLDivElement | null = null
let root: Root | null = null

beforeEach(() => {
  mockPush.mockClear()
  mockItems = []
  mockDetails = []
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  container = null
  root = null
  document.body.innerHTML = ""
})

async function renderPage() {
  const module = await import("./page")
  const Page = module.default

  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(<Page />)
  })
}

describe("BetaReadsPage", () => {
  it("shows author questions and the final-feedback completion gate on active assignments", async () => {
    mockItems = [
      {
        id: "assignment-1",
        book_id: "book-1",
        author_user_id: "author-1",
        reader_user_id: "reader-1",
        reader_email: "reader@example.com",
        collaborator_id: "collab-1",
        state: "active",
        view_bucket: "active",
        task_label: "First-pass beta read",
        scope_kind: "full_book",
        section_label: null,
        chapter_start: null,
        chapter_end: null,
        window_days: 3,
        required_progress_pct: 100,
        required_comment_count: 3,
        required_feedback_item_count: 1,
        require_final_feedback: true,
        starts_at: "2026-06-06T00:00:00Z",
        expires_at: "2026-06-09T00:00:00Z",
        access_granted_at: "2026-06-06T00:00:00Z",
        submitted_at: null,
        completed_at: null,
        first_opened_at: null,
        missed_reason: null,
        counted_toward_missed_streak: false,
        revoked_at: null,
        revoked_reason: null,
        disqualified_at: null,
        disqualified_reason: null,
        book_title: "Sky of Ash",
        author_name: "Author One",
        book_route_title: "sky-of-ash",
        progress_pct: 42,
        chapters_total: 10,
        chapters_read_count: 4,
        comment_count: 1,
        feedback_item_count: 0,
        question_count: 2,
        answered_question_count: 0,
        current_chapter: 4,
        status_label: "Active",
        primary_action: "Continue",
        submission_allowed: false,
        is_overdue: false,
        consecutive_missed_beta_reads: 0,
        penalty_status: "clear",
        penalty_warning: null,
        final_rating: null,
        rating_sentiment: null,
        book_average_rating: null,
        book_rating_count: 0,
      },
    ]
    mockDetails = [
      {
        isLoading: false,
        data: {
          assignment: mockItems[0] as never,
          author_questions: [
            { id: "q-1", prompt: "What confused you most?", created_at: "2026-06-06T00:00:00Z", answer_count: 0 },
            { id: "q-2", prompt: "Which moment landed best?", created_at: "2026-06-06T00:00:00Z", answer_count: 0 },
          ],
          feedback_items: [],
          feedback_summary: {
            feedback_item_count: 0,
            chapter_comment_count: 0,
            scene_reaction_count: 0,
            answer_count: 0,
            confusing_count: 0,
            boring_count: 0,
            favorite_count: 0,
          },
        },
      },
    ]

    await renderPage()

    expect(container?.textContent).toContain("Author questions")
    expect(container?.textContent).toContain("What confused you most?")
    expect(container?.textContent).toContain("Which moment landed best?")
    expect(container?.textContent).toContain("Require final feedback before completion")
  })
})
