import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { betaReadsApi } from "@/lib/api/betaReads"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { parseQuestionLines, selectPrimaryAssignment } from "@/lib/utils/betaRead"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import { canEditFeedback, reviewRequirements, validateFeedback, validateInvitation, validateQuestions } from "./betaFeedbackPage.helpers"
import type { BetaReadAssignment, BetaReadAssignmentDetail } from "@/types/betaRead"

export function useBetaFeedbackWorkspace(bookId: string) {
  const client = useQueryClient()
  const lock = useRef(false)
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [invitationDirty, setInvitationDirty] = useState(false)
  const [selectedAuthorAssignmentId, setSelectedAuthorAssignmentId] = useState<string | null>(null)
  const [selectedReaderId, setSelectedReaderId] = useState<string | null>(null)
  const authorListKey = asQueryKey(`beta-feedback:${bookId}:author-assignments`)
  const readerListKey = asQueryKey(`beta-feedback:${bookId}:my-assignments`)
  const authorKey = (id: string) => asQueryKey(`beta-feedback:${bookId}:author-detail:${id}`)
  const readerKey = (id: string) => asQueryKey(`beta-feedback:${bookId}:reader-detail:${id}`)
  const bookQuery = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "detail")), queryFn: () => booksApi.get(bookId), retry: false })
  const book = bookQuery.data ?? null
  const isAuthorView = Boolean(book && book.workspace_shell === "author" && book.access_class !== "reader_collaborator")
  const authorListQuery = useQuery({ queryKey: authorListKey, queryFn: () => betaReadsApi.listBookAssignments(bookId), enabled: isAuthorView, retry: false, refetchOnWindowFocus: false })
  const readerListQuery = useQuery({ queryKey: readerListKey, queryFn: () => betaReadsApi.listMine(), enabled: !!book && !isAuthorView, retry: false, refetchOnWindowFocus: false })
  const authorAssignments = authorListQuery.data ?? []
  const myAssignments = useMemo(() => (readerListQuery.data ?? []).filter((entry) => entry.book_id === normalizeBookRouteId(bookId)), [readerListQuery.data, bookId])
  const primaryReaderAssignment = selectedReaderId ? myAssignments.find((entry) => entry.id === selectedReaderId) ?? null : selectPrimaryAssignment(myAssignments, bookId)
  const authorSelectionMissing = !!selectedAuthorAssignmentId && !!authorListQuery.data && !authorAssignments.some((entry) => entry.id === selectedAuthorAssignmentId)
  const authorQuery = useQuery({ queryKey: authorKey(selectedAuthorAssignmentId ?? "none"), queryFn: () => betaReadsApi.getBookAssignmentDetail(bookId, selectedAuthorAssignmentId!), enabled: isAuthorView && !!selectedAuthorAssignmentId && !authorSelectionMissing, retry: false, refetchOnWindowFocus: false })
  const readerQuery = useQuery({ queryKey: readerKey(primaryReaderAssignment?.id ?? "none"), queryFn: () => betaReadsApi.getMineDetail(primaryReaderAssignment!.id), enabled: !isAuthorView && !!primaryReaderAssignment, retry: false, refetchOnWindowFocus: false })
  const authorDetail = authorSelectionMissing ? null : authorQuery.data ?? null
  const readerDetail = readerQuery.data ?? null
  const loading = bookQuery.isLoading || (isAuthorView ? authorListQuery.isLoading : readerListQuery.isLoading)
  const [readerEmail, setReaderEmail] = useState("")
  const [taskLabel, setTaskLabel] = useState("First-pass reader response")
  const [sectionLabel, setSectionLabel] = useState("" )
  const [scopeKind, setScopeKind] = useState("full_book")
  const [chapterStart, setChapterStart] = useState("1")
  const [chapterEnd, setChapterEnd] = useState("3")
  const [windowDays, setWindowDays] = useState("7")
  const [requiredProgressPct, setRequiredProgressPct] = useState("100")
  const [requiredCommentCount, setRequiredCommentCount] = useState("1")
  const [requiredFeedbackItemCount, setRequiredFeedbackItemCount] = useState("2")
  const [authorQuestionsText, setAuthorQuestionsText] = useState("Did Chapter 3 hook you?\nWhere did you get confused?")
  const [questionDrafts, setQuestionDrafts] = useState<Record<string, string>>({})

  const [feedbackKind, setFeedbackKind] = useState("chapter_comment")
  const [feedbackChapter, setFeedbackChapter] = useState("1")
  const [feedbackReaction, setFeedbackReaction] = useState("")
  const [feedbackAnchor, setFeedbackAnchor] = useState("")
  const [feedbackBody, setFeedbackBody] = useState("")
  const [selectedQuestionId, setSelectedQuestionId] = useState("")
  const [finalReview, setFinalReview] = useState("")
  const [finalRating, setFinalRating] = useState("4")
  const [requirementsModal, setRequirementsModal] = useState<string[] | null>(null)
  const initializedReaderId = useRef<string | null>(null)
  const readerId = readerDetail?.assignment.id
  const readerStart = readerDetail?.assignment.chapter_start
  useEffect(() => {
    if (!readerId || initializedReaderId.current === readerId) return
    initializedReaderId.current = readerId
    setFeedbackChapter(String(readerStart ?? 1))
  }, [readerId, readerStart])

  const extraQuestionsText = questionDrafts[selectedAuthorAssignmentId ?? ""] ?? ""
  const setExtraQuestionsText = (value: string) => setQuestionDrafts((current) => ({ ...current, [selectedAuthorAssignmentId ?? ""]: value }))
  const canLeaveFeedback = Boolean(book?.collaboration_permissions?.can_comment || book?.collaboration_permissions?.can_edit_manuscript)
  const readerWritable = !!readerDetail && canLeaveFeedback && canEditFeedback(readerDetail.assignment)
  const authorWritable = !!authorDetail && ["active", "scheduled"].includes(authorDetail.assignment.view_bucket)
  const readerDirty = !!(feedbackReaction.trim() || feedbackAnchor.trim() || feedbackBody.trim() || selectedQuestionId || finalReview.trim())
  const leaveGuard = useRef(false)
  leaveGuard.current = saving || invitationDirty || Object.values(questionDrafts).some((text) => text.trim()) || readerDirty
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (leaveGuard.current) { event.preventDefault(); event.returnValue = "" } }
    const click = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!leaveGuard.current || !link || link.target === "_blank" || link.hasAttribute("download") || event.ctrlKey || event.metaKey || new URL(link.href).pathname === location.pathname) return
      if (!window.confirm("Leave Beta feedback? Unsaved drafts will be lost, and an in-progress save may still complete.")) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", click, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true) }
  }, [])
  const refreshAuthorDetail = (id: string) => { if (!lock.current) setSelectedAuthorAssignmentId(id) }
  const selectReader = (id: string) => {
    if (lock.current || (readerDirty && !window.confirm("Discard unsaved feedback and final review before changing assignments?"))) return
    setFeedbackBody(""); setFeedbackAnchor(""); setFeedbackReaction(""); setSelectedQuestionId(""); setFeedbackKind("chapter_comment"); setFeedbackChapter(""); setFinalReview(""); setFinalRating("4"); setSelectedReaderId(id)
  }
  const updateAssignment = (assignment: BetaReadAssignment, author: boolean) => {
    client.setQueryData<BetaReadAssignment[]>(author ? authorListKey : readerListKey, (current = []) => [assignment, ...current.filter((entry) => entry.id !== assignment.id)])
    client.setQueryData<BetaReadAssignmentDetail>(author ? authorKey(assignment.id) : readerKey(assignment.id), (current) => current ? { ...current, assignment } : current)
  }
  async function run(work: () => Promise<void>, fallback: string) {
    if (lock.current) return
    lock.current = true; setSaving(true); setStatus(null)
    try {
      await client.cancelQueries({ predicate: (query) => typeof query.queryKey[0] === "string" && query.queryKey[0].startsWith(`beta-feedback:${bookId}:`) })
      await work()
    }
    catch (error) { setStatus(`${getApiErrorDetail(error) ?? fallback} Your draft is retained. Refresh this assignment before retrying to check whether the update was saved.`) }
    finally { lock.current = false; setSaving(false) }
  }
  async function createAssignment() {
    const draft = { readerEmail, taskLabel, scopeKind, sectionLabel, chapterStart, chapterEnd, windowDays, requiredProgressPct, requiredCommentCount, requiredFeedbackItemCount, authorQuestionsText }
    const error = validateInvitation(draft, book?.total_chapters ?? 0)
    if (error) { setStatus(error); return }
    await run(async () => {
      const created = await betaReadsApi.createAssignment(bookId, {
        readerEmail: readerEmail.trim(), taskLabel: taskLabel.trim(), scopeKind, sectionLabel: scopeKind === "section" ? sectionLabel.trim() : null,
        chapterStart: scopeKind === "full_book" ? null : Number(chapterStart), chapterEnd: scopeKind === "full_book" ? null : Number(chapterEnd),
        windowDays: Number(windowDays), requiredProgressPct: Number(requiredProgressPct), requiredCommentCount: Number(requiredCommentCount), requiredFeedbackItemCount: Number(requiredFeedbackItemCount), requireFinalFeedback: true, authorQuestions: parseQuestionLines(authorQuestionsText),
      })
      updateAssignment(created, true); setSelectedAuthorAssignmentId(created.id); setReaderEmail(""); setInvitationDirty(false); setCreateOpen(false); setStatus("Beta read assignment created.")
    }, "Could not confirm the new assignment.")
  }
  async function appendQuestions() {
    if (!authorDetail || !authorWritable || !extraQuestionsText.trim()) return
    const error = validateQuestions(extraQuestionsText)
    if (error) { setStatus(error); return }
    const id = authorDetail.assignment.id
    await run(async () => {
      const questions = await betaReadsApi.appendQuestions(bookId, id, parseQuestionLines(extraQuestionsText))
      client.setQueryData<BetaReadAssignmentDetail>(authorKey(id), (current) => current ? { ...current, author_questions: questions, assignment: { ...current.assignment, question_count: questions.length } } : current)
      setQuestionDrafts((current) => ({ ...current, [id]: "" })); setStatus("Questions added.")
    }, "Could not confirm those questions.")
  }
  async function revokeAssignment(id: string) {
    if (lock.current || !window.confirm("Revoke this beta read? The reader will lose assignment access. Existing feedback will remain available.")) return
    await run(async () => { updateAssignment(await betaReadsApi.revokeAssignment(bookId, id), true); setStatus("Assignment revoked. Existing feedback remains available.") }, "Could not revoke this assignment.")
  }
  async function startAssignment() {
    if (!readerDetail || !readerWritable) return
    await run(async () => { updateAssignment(await betaReadsApi.start(readerDetail.assignment.id), false); setStatus("Beta read started.") }, "Could not start this beta read.")
  }
  async function createFeedbackItem() {
    if (!readerDetail || !canLeaveFeedback) return
    const error = validateFeedback({ feedbackKind, feedbackChapter, feedbackReaction, feedbackAnchor, feedbackBody, selectedQuestionId }, readerDetail, book?.total_chapters ?? 0)
    if (error) { setStatus(error); return }
    const id = readerDetail.assignment.id
    await run(async () => {
      const updated = await betaReadsApi.createFeedbackItem(id, { kind: feedbackKind, chapterNumber: feedbackChapter ? Number(feedbackChapter) : null, questionId: selectedQuestionId || null, reaction: feedbackReaction.trim() || null, anchorText: feedbackAnchor.trim() || null, body: feedbackBody.trim() || null })
      client.setQueryData(readerKey(id), updated); updateAssignment(updated.assignment, false)
      setFeedbackKind("chapter_comment"); setFeedbackReaction(""); setFeedbackAnchor(""); setFeedbackBody(""); setSelectedQuestionId(""); setStatus("Feedback saved. You can add another item or complete your final review.")
    }, "Could not confirm this feedback item.")
  }
  async function deleteFeedbackItem(itemId: string) {
    if (lock.current || !readerDetail || !readerWritable || !window.confirm("Remove this feedback item? This cannot be undone and may affect your assignment requirements.")) return
    const id = readerDetail.assignment.id
    await run(async () => { const updated = await betaReadsApi.deleteFeedbackItem(id, itemId); client.setQueryData(readerKey(id), updated); updateAssignment(updated.assignment, false); setStatus("Feedback removed.") }, "Could not remove this feedback item.")
  }
  async function submitReview() {
    if (!readerDetail || !readerWritable) return
    if (finalReview.trim().length < 3 || finalReview.trim().length > 20000) { setStatus("Write a final review between 3 and 20,000 characters."); return }
    const rating = Number(finalRating)
    if (!Number.isFinite(rating) || rating < 1 || rating > 5 || rating * 2 !== Math.round(rating * 2)) { setStatus("Choose a rating from 1 to 5 in half-point steps."); return }
    const issues = reviewRequirements(readerDetail)
    if (issues.length) { setRequirementsModal(issues); return }
    await run(async () => { updateAssignment(await betaReadsApi.submitReview(readerDetail.assignment.id, finalReview.trim(), rating), false); setFinalReview(""); setStatus("Review submitted. Your final review and rating have been saved.") }, "Could not confirm the final review.")
  }
  const requests = [{ label: "manuscript", query: bookQuery }, ...(isAuthorView ? [{ label: "assignments", query: authorListQuery }, ...(selectedAuthorAssignmentId && !authorSelectionMissing ? [{ label: "selected responses", query: authorQuery }] : [])] : book ? [{ label: "your assignments", query: readerListQuery }, ...(primaryReaderAssignment ? [{ label: "your feedback", query: readerQuery }] : [])] : [])]
  const unavailable = bookQuery.isError && !book || (isAuthorView ? authorListQuery.isError && !authorListQuery.data : readerListQuery.isError && !readerListQuery.data)
  return {
    book, status, saving, createOpen, setCreateOpen, setInvitationDirty, isAuthorView, authorAssignments, authorDetail, readerDetail, loading, unavailable, requests, authorQuery, readerQuery, authorSelectionMissing, selectedAuthorAssignmentId, primaryReaderAssignment, myAssignments, selectReader, authorWritable, readerWritable, canLeaveFeedback,
    readerEmail, setReaderEmail, taskLabel, setTaskLabel, scopeKind, setScopeKind, sectionLabel, setSectionLabel, chapterStart, setChapterStart, chapterEnd, setChapterEnd, windowDays, setWindowDays, requiredProgressPct, setRequiredProgressPct, requiredCommentCount, setRequiredCommentCount, requiredFeedbackItemCount, setRequiredFeedbackItemCount, authorQuestionsText, setAuthorQuestionsText, extraQuestionsText, setExtraQuestionsText,
    feedbackKind, setFeedbackKind, feedbackChapter, setFeedbackChapter, feedbackReaction, setFeedbackReaction, feedbackAnchor, setFeedbackAnchor, feedbackBody, setFeedbackBody, selectedQuestionId, setSelectedQuestionId, finalReview, setFinalReview, finalRating, setFinalRating, requirementsModal, setRequirementsModal,
    refreshAuthorDetail, createAssignment, appendQuestions, revokeAssignment, startAssignment, createFeedbackItem, deleteFeedbackItem, submitReview,
  }
}

export type BetaFeedbackWorkspace = ReturnType<typeof useBetaFeedbackWorkspace>
