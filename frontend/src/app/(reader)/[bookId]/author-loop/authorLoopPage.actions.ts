import { useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { booksApi } from "@/lib/api/books"
import { betaReadsApi } from "@/lib/api/betaReads"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import { parseDeadlineWindow, validateAuthorLoopInvite, type AuthorLoopIssueCard } from "@/lib/utils/authorLoop"
import { applyRevisionBoardState, buildRevisionTask, todayDateKey } from "@/lib/utils/revisionIntelligence"
import type { WriterWorkspace } from "@/types/book"
import type { BetaReadAssignment, BetaReadAssignmentDetail, BetaReadFeedbackItem } from "@/types/betaRead"

export function useAuthorLoopActions({ bookId, totalChapters, writerWorkspace, issueCards, selectedAssignment, draft, setReaderEmail, setSelectedAssignmentId, setStatusMessage }: {
  bookId: string; totalChapters: number; writerWorkspace: WriterWorkspace | null; issueCards: AuthorLoopIssueCard[]; selectedAssignment: BetaReadAssignmentDetail | null
  draft: { readerEmail: string; scopeKind: string; chapterStart: string; chapterEnd: string; deadline: string; authorQuestions: string }
  setReaderEmail: (value: string) => void; setSelectedAssignmentId: (value: string) => void; setStatusMessage: (value: string | null) => void
}) {
  const client = useQueryClient()
  const lock = useRef(false)
  const [creatingAssignment, setCreatingAssignment] = useState(false)
  const [savingIssueId, setSavingIssueId] = useState<string | null>(null)
  const [savingFeedbackId, setSavingFeedbackId] = useState<string | null>(null)
  const [copyingLink, setCopyingLink] = useState(false)
  const [guestLink, setGuestLink] = useState<{ assignmentId: string; url: string } | null>(null)
  const [lastDismissedId, setLastDismissedId] = useState<string | null>(null)
  const dismissedStatus = useRef<"pending" | "task_created">("pending")
  const workspaceKey = asQueryKey(bookCacheKey(bookId, "writer-workspace"))
  const currentWorkspace = () => client.getQueryData<WriterWorkspace>(workspaceKey) ?? writerWorkspace

  async function saveWorkspacePatch(patch: Partial<WriterWorkspace>) {
    const updated = await booksApi.updateWriterWorkspace(bookId, patch)
    client.setQueryData(workspaceKey, updated)
    return updated
  }

  async function handleIssueStatus(issueId: string, status: "ignored" | "task_created" | "pending") {
    const workspace = currentWorkspace()
    if (lock.current || !workspace) return
    lock.current = true; setSavingIssueId(issueId); setStatusMessage(null)
    try {
      let calendar = workspace.goal_calendar
      let taskId: string | undefined
      if (status === "task_created") {
        const issue = issueCards.find((item) => item.id === issueId)
        if (!issue) return
        taskId = `revision-task:${issueId}`
        if (!calendar.some((task) => task.id === taskId)) calendar = [{ id: taskId, title: issue.title, due_date: todayDateKey(), quota_value: 1, quota_unit: "tasks", completed: false }, ...calendar]
      }
      const nextStatus = status === "pending" && lastDismissedId === issueId ? dismissedStatus.current : status
      const previousStatus = workspace.revision_board.items.find((item) => item.item_id === issueId)?.status ?? issueCards.find((item) => item.id === issueId)?.status
      const board = applyRevisionBoardState(workspace.revision_board, issueId, { status: nextStatus, ...(taskId ? { task_id: taskId } : {}), updated_at: new Date().toISOString() })
      await saveWorkspacePatch({ revision_board: board, goal_calendar: calendar })
      if (status === "ignored") dismissedStatus.current = previousStatus === "task_created" ? "task_created" : "pending"
      setLastDismissedId(status === "ignored" ? issueId : null)
      setStatusMessage(status === "task_created" ? "Added to your revision queue." : status === "ignored" ? "Dismissed from the active queue. You can undo this decision below." : "Restored the finding to the active queue.")
    } catch (error) { setStatusMessage(`${getApiErrorDetail(error) ?? "Could not update that finding."} Your previous decision is retained. Refresh the revision queue before retrying.`) }
    finally { lock.current = false; setSavingIssueId(null) }
  }

  async function handleCreateAssignment() {
    if (lock.current) return
    const validation = validateAuthorLoopInvite(draft, totalChapters)
    if (validation) { setStatusMessage(validation); return }
    lock.current = true; setCreatingAssignment(true); setStatusMessage(null)
    try {
      const created = await betaReadsApi.createAssignment(bookId, {
        readerEmail: draft.readerEmail.trim(), taskLabel: draft.scopeKind === "full_book" ? "Focused beta read" : `Scoped beta read: chapters ${draft.chapterStart}-${draft.chapterEnd}`,
        scopeKind: draft.scopeKind, chapterStart: draft.scopeKind === "full_book" ? null : Number(draft.chapterStart), chapterEnd: draft.scopeKind === "full_book" ? null : Number(draft.chapterEnd),
        windowDays: parseDeadlineWindow(draft.deadline)!, requiredProgressPct: 100, requiredCommentCount: 0, requiredFeedbackItemCount: 1, requireFinalFeedback: true,
        authorQuestions: draft.authorQuestions.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),
      })
      client.setQueryData<BetaReadAssignment[]>(asQueryKey(`author-loop:${bookId}:beta-assignments`), (current = []) => [created, ...current.filter((assignment) => assignment.id !== created.id)])
      setSelectedAssignmentId(created.id); setReaderEmail("")
      setStatusMessage(`Invitation created for ${draft.readerEmail.trim()} with the selected manuscript scope. Check its status in Reader feedback.`)
    } catch (error) { setStatusMessage(`${getApiErrorDetail(error) ?? "Could not confirm the beta-reader invitation."} Your draft is retained. Refresh assignments before retrying to avoid a duplicate invite.`) }
    finally { lock.current = false; setCreatingAssignment(false) }
  }

  async function handleCopyGuestLink() {
    if (lock.current || !selectedAssignment) return
    lock.current = true; setCopyingLink(true); setStatusMessage(null)
    const id = selectedAssignment.assignment.id
    try {
      const result = await betaReadsApi.getGuestLink(bookId, id)
      setGuestLink({ assignmentId: id, url: result.share_url })
      try { await navigator.clipboard.writeText(result.share_url); setStatusMessage("Private review link copied.") }
      catch { setStatusMessage("The private review link is ready. Clipboard access failed; select and copy the link shown below.") }
    } catch (error) { setStatusMessage(getApiErrorDetail(error) ?? "Could not load the private review link. Try again.") }
    finally { lock.current = false; setCopyingLink(false) }
  }

  async function handleFeedbackStatus(item: BetaReadFeedbackItem, status: "resolved" | "archived" | "task_created" | "open") {
    const workspace = currentWorkspace()
    if (lock.current || !selectedAssignment || (status === "task_created" && !workspace)) return
    lock.current = true; setSavingFeedbackId(item.id); setStatusMessage(null)
    const assignmentId = selectedAssignment.assignment.id
    let taskSaved = false
    try {
      let taskId = item.author_task_id ?? null
      if (status === "task_created" && workspace) {
        const task = buildRevisionTask({ id: `beta-feedback:${item.id}`, category: "beta_feedback", title: item.chapter_number ? `Review beta feedback from chapter ${item.chapter_number}` : "Review beta feedback", description: item.body || item.anchor_text || item.question_prompt || "Follow up on beta-reader feedback.", severity: "medium", status: "pending" })
        taskId = task.id
        if (!workspace.goal_calendar.some((existing) => existing.id === task.id)) await saveWorkspacePatch({ goal_calendar: [task, ...workspace.goal_calendar] })
        taskSaved = true
      }
      const updated = await betaReadsApi.updateBookFeedbackItem(bookId, assignmentId, item.id, { authorStatus: status, authorTaskId: taskId })
      client.setQueryData(asQueryKey(`author-loop:${bookId}:beta-detail:${assignmentId}`), updated)
      setStatusMessage(status === "task_created" ? "Added to your revision queue." : status === "resolved" ? "Feedback resolved. This does not edit the manuscript." : status === "open" ? "Feedback reopened." : "Feedback archived. Reopen it here if needed.")
    } catch (error) { setStatusMessage(taskSaved ? "The revision task was saved, but the feedback status could not update. Retry to link the existing task without creating another." : `${getApiErrorDetail(error) ?? "Could not update that feedback item."} The previous feedback remains available. Try again.`) }
    finally { lock.current = false; setSavingFeedbackId(null) }
  }

  return { creatingAssignment, savingIssueId, savingFeedbackId, copyingLink, guestLink, lastDismissedId, busy: creatingAssignment || !!savingIssueId || !!savingFeedbackId || copyingLink, handleIssueStatus, handleCreateAssignment, handleCopyGuestLink, handleFeedbackStatus }
}
