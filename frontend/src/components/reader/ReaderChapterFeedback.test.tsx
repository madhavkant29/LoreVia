import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { ManuscriptAnnotation } from "@/types/book"
import type { ChapterBetaFeedback } from "@/types/reader"

const useBookDetailMock = vi.hoisted(() => vi.fn())
const useQueryMock = vi.hoisted(() => vi.fn())
const createFeedbackItemMock = vi.hoisted(() => vi.fn())
const saveManuscriptAnnotationMock = vi.hoisted(() => vi.fn())

vi.mock("@/lib/hooks/useBookDetail", () => ({
  useBookDetail: useBookDetailMock,
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
}))

vi.mock("@/lib/api/betaReads", () => ({
  betaReadsApi: {
    createFeedbackItem: createFeedbackItemMock,
    listMine: vi.fn(),
  },
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    getManuscriptAnnotations: vi.fn(),
    saveManuscriptAnnotation: saveManuscriptAnnotationMock,
  },
}))

import { ReaderChapterFeedback } from "./ReaderChapterFeedback"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("ReaderChapterFeedback", () => {
  beforeEach(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    useBookDetailMock.mockReset()
    useQueryMock.mockReset()
    createFeedbackItemMock.mockReset()
    saveManuscriptAnnotationMock.mockReset()
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    if (container) {
      container.remove()
    }
    container = null
    root = null
  })

  it("renders beta reader comments and owner comment controls at the bottom of the chapter", () => {
    useBookDetailMock.mockReturnValue({
      data: {
        id: "book-1",
        access_class: "owner",
        workspace_shell: "author",
      },
    })
    useQueryMock.mockReturnValue({ data: [], refetch: vi.fn(), isLoading: false })

    const feedback: ChapterBetaFeedback[] = [
      {
        id: "feedback-1",
        assignment_id: "assignment-1",
        collaborator_id: "collab-1",
        reader_user_id: "reader-1",
        reader_email: "beta@example.com",
        reader_display_name: "Beta Reader",
        task_label: "Full manuscript pass",
        kind: "chapter_comment",
        chapter_number: 4,
        body: "The chapter turn lands, but the reveal wants one more setup line.",
        anchor_text: null,
        author_status: "open",
        created_at: "2026-05-27T10:00:00.000Z",
        updated_at: "2026-05-27T10:00:00.000Z",
      },
    ]

    const view = renderComponent({ chapterFeedback: feedback })

    expect(view.textContent).toContain("Leave a chapter comment")
    expect(view.textContent).toContain("Beta Reader")
    expect(view.textContent).toContain("The chapter turn lands, but the reveal wants one more setup line.")
    expect(view.querySelector("textarea")).not.toBeNull()
  })

  it("renders shared manuscript annotations below the chapter for author collaborators", () => {
    useBookDetailMock.mockReturnValue({
      data: {
        id: "book-1",
        access_class: "author_collaborator",
        workspace_shell: "author",
        collaboration_permissions: {
          can_edit_manuscript: true,
          can_comment: true,
        },
      },
    })
    const annotation: ManuscriptAnnotation = {
      id: "annotation-1",
      book_id: "book-1",
      book_title: "Sky of Ash",
      chapter_number: 4,
      chapter_title: "The Ember Gate",
      category: "general",
      visibility: "shared",
      quote: "The gate flared open",
      comment: "Keep the gate language consistent for every collaborator.",
      created_by_user_id: "editor-1",
      created_by_label: "Editor One",
      can_edit: true,
      status: "open",
      resolved_at: null,
      created_at: "2026-05-27T09:00:00.000Z",
      updated_at: "2026-05-27T09:00:00.000Z",
    }
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      if (Array.isArray(queryKey) && String(queryKey[0]).includes("annotations")) {
        return { data: [annotation], refetch: vi.fn(), isLoading: false }
      }
      return { data: [], refetch: vi.fn(), isLoading: false }
    })

    const view = renderComponent({ chapterFeedback: [] })

    expect(view.textContent).toContain("1 chapter comment visible here")
    expect(view.textContent).toContain("Editor One")
    expect(view.textContent).toContain("Keep the gate language consistent for every collaborator.")
    expect(view.textContent).toContain("The gate flared open")
  })

  it("sends chapter comments through beta feedback when an active beta assignment exists", async () => {
    useBookDetailMock.mockReturnValue({
      data: {
        id: "book-1",
        access_class: "reader_collaborator",
        workspace_shell: "reader",
        collaboration_permissions: {
          can_comment: true,
        },
      },
    })
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      if (Array.isArray(queryKey) && queryKey[0] === "reader:beta-reads") {
        return {
          data: [
            {
              id: "assignment-2",
              book_id: "book-1",
              reader_user_id: "reader-9",
              reader_email: "beta@example.com",
              collaborator_id: "collab-9",
              task_label: "Chapter pass",
              chapter_start: 5,
              chapter_end: 5,
            },
          ],
          refetch: vi.fn(),
          isLoading: false,
        }
      }
      return {
        data: [],
        refetch: vi.fn(),
        isLoading: false,
      }
    })
    createFeedbackItemMock.mockResolvedValue({
      feedback_items: [
        {
          id: "feedback-22",
          kind: "chapter_comment",
          chapter_number: 5,
          body: "This beat is stronger once the dialogue sharpens.",
          anchor_text: null,
          author_status: "open",
          created_at: "2026-05-27T11:00:00.000Z",
          updated_at: "2026-05-27T11:00:00.000Z",
        },
      ],
    })

    const view = renderComponent({ chapterNum: 5, chapterFeedback: [] })
    const textarea = view.querySelector("textarea")
    const button = Array.from(view.querySelectorAll("button")).find((item) => item.textContent?.includes("Leave chapter comment"))

    expect(textarea).not.toBeNull()
    expect(button).not.toBeNull()

    act(() => {
      if (textarea instanceof HTMLTextAreaElement) {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set
        nativeSetter?.call(textarea, "This beat is stronger once the dialogue sharpens.")
        textarea.dispatchEvent(new Event("input", { bubbles: true }))
      }
    })

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(createFeedbackItemMock).toHaveBeenCalledWith("assignment-2", {
      kind: "chapter_comment",
      chapterNumber: 5,
      body: "This beat is stronger once the dialogue sharpens.",
    })
    expect(saveManuscriptAnnotationMock).not.toHaveBeenCalled()
    expect(view.textContent).toContain("This beat is stronger once the dialogue sharpens.")
  })
})

function renderComponent({
  bookId = "book-1",
  chapterNum = 4,
  chapterFeedback = [],
}: {
  bookId?: string
  chapterNum?: number
  chapterFeedback?: ChapterBetaFeedback[]
}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <ReaderChapterFeedback
        bookId={bookId}
        chapterNum={chapterNum}
        theme="light"
        chapterFeedback={chapterFeedback}
      />
    )
  })

  return container
}
