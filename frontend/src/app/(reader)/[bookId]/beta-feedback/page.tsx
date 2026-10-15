"use client"

import { useParams } from "next/navigation"
import Link from "next/link"
import type { Route } from "next"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { Dialog } from "@/components/ui/Dialog"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatFeedbackKindLabel, parseQuestionLines } from "@/lib/utils/betaRead"
import { LabeledField, StatPill } from "./betaFeedbackPage.components"
import { ReaderFeedbackPanel } from "./betaFeedbackPage.reader"
import { useBetaFeedbackWorkspace } from "./betaFeedbackPage.state"

export default function BetaFeedbackPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <BetaFeedbackWorkspace key={bookId} bookId={bookId} />
}

function BetaFeedbackWorkspace({ bookId }: { bookId: string }) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const workspace = useBetaFeedbackWorkspace(bookId)
  const { book, status, saving, createOpen, setCreateOpen, setInvitationDirty, isAuthorView, authorAssignments, authorDetail, readerDetail, loading, unavailable, requests, selectedAuthorAssignmentId, primaryReaderAssignment, myAssignments, selectReader, authorWritable,
    readerEmail, setReaderEmail, taskLabel, setTaskLabel, scopeKind, setScopeKind, sectionLabel, setSectionLabel, chapterStart, setChapterStart, chapterEnd, setChapterEnd, windowDays, setWindowDays, requiredProgressPct, setRequiredProgressPct, requiredCommentCount, setRequiredCommentCount, requiredFeedbackItemCount, setRequiredFeedbackItemCount, authorQuestionsText, setAuthorQuestionsText, extraQuestionsText, setExtraQuestionsText,
    requirementsModal, setRequirementsModal, refreshAuthorDetail, createAssignment, appendQuestions, revokeAssignment } = workspace
  return (
    <>
    <div data-beta-feedback-workspace className={`min-h-screen ${isDark ? "text-slate-100" : "text-stone-950"}`}>
      <div className="mx-auto max-w-6xl space-y-5 px-4 pb-28 pt-5 sm:px-6 lg:px-8">
        <main className="min-w-0 space-y-5">
          <WorkspaceFamilyHeader
            active="beta-feedback"
            bookId={bookId}
            family="publish-export"
            title="Beta feedback"
            description={isAuthorView ? `Assign readers to ${book?.title ?? "this manuscript"}, then review their responses.` : `Read your assigned scope in ${book?.title ?? "this manuscript"}, save feedback, and complete your review.`}
            actions={<><Link href={(isAuthorView ? `/${bookId}/author-loop` : `/${bookId}`) as Route} className="app-button-secondary">{isAuthorView ? "Revision workflow" : "Continue reading"}</Link><button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))}>Help</button></>}
          />
          {status ? <p role="status" className="border-l-2 border-[rgb(var(--accent))] pl-3 text-sm">{status}</p> : null}
          <div className="space-y-3">
            {requests.filter(({ query }) => query.isError).map(({ label, query }) => <div key={label} role="alert"><p>Could not load or refresh {label}. Previously loaded content is retained.</p><button type="button" className="app-button-secondary mt-2" disabled={saving || query.isFetching} onClick={() => void query.refetch()}>Retry {label}</button></div>)}
            <button type="button" className="app-button-secondary" disabled={saving || requests.some(({ query }) => query.isFetching)} onClick={() => void Promise.allSettled(requests.map(({ query }) => query.refetch()))}>Refresh workspace</button>
          </div>
          <fieldset className="min-w-0 space-y-5 border-0 p-0" disabled={saving} hidden={!!unavailable}>
          {!isAuthorView && myAssignments.length > 1 ? <LabeledField label="Your assignment" isDark={isDark}><select aria-label="Your assignment" value={primaryReaderAssignment?.id ?? ""} onChange={(event) => selectReader(event.target.value)} className="min-h-11 border border-[rgb(var(--border))] bg-[rgb(var(--background))] px-3"><option value="" disabled>Choose an assignment</option>{myAssignments.map((assignment) => <option key={assignment.id} value={assignment.id}>{assignment.task_label} · {assignment.status_label}</option>)}</select></LabeledField> : null}
          {!isAuthorView && workspace.readerQuery.isLoading ? <p role="status">Loading your feedback…</p> : null}
          {loading ? (
            <section className={`rounded-none border p-6 text-sm ${isDark ? "border-white/[0.065] bg-[#0d141c] text-slate-400" : "border-slate-200/70 bg-white text-slate-500"}`}>
              Loading beta feedback workspace...
            </section>
          ) : null}

          {!loading && isAuthorView ? (
            <section className="flex flex-col gap-5">
              {createOpen ? <div id="new-assignment" onChange={() => setInvitationDirty(true)} className={`order-1 border-y py-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
<div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Create beta read</h2><button type="button" className="app-button-secondary" onClick={() => setCreateOpen(false)}>Hide assignment form</button></div><p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Hidden drafts stay on this page until you leave. Creating an assignment grants the selected reader access.</p>
                <div className="mt-5 grid gap-3">
                  <LabeledField label="Reader email" detail="Invite the account that should receive read-only beta access." isDark={isDark}>
                    <input
                      value={readerEmail}
                      onChange={(event) => setReaderEmail(event.target.value)}
                      aria-label="Reader email" type="email" maxLength={320}
                      className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    />
                  </LabeledField>
                  <LabeledField label="Task label" detail="Name the pass so the reader knows what kind of feedback you want." isDark={isDark}>
                    <input
                      value={taskLabel}
                      onChange={(event) => setTaskLabel(event.target.value)}
                      aria-label="Task label" maxLength={200}
                      className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    />
                  </LabeledField>
                  <LabeledField label="Scope" detail="Choose whether this beta read covers the full manuscript or a narrowed packet." isDark={isDark}>
                    <select
                      value={scopeKind}
                      onChange={(event) => setScopeKind(event.target.value)}
                      aria-label="Scope"
                      className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    >
                      <option value="full_book">Full book</option>
                      <option value="chapter_range">Chapter range</option>
                      <option value="section">Section</option>
                    </select>
                  </LabeledField>
                  {scopeKind === "section" ? <LabeledField label="Section label" detail="Name the selected chapter packet." isDark={isDark}><input aria-label="Section label" value={sectionLabel} maxLength={200} onChange={(event) => setSectionLabel(event.target.value)} className="h-11 border border-[rgb(var(--border))] bg-[rgb(var(--background))] px-3" /></LabeledField> : null}
                  {scopeKind !== "full_book" ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <LabeledField label="From chapter" isDark={isDark}>
                        <input
                          type="number"
                          min="1"
                          value={chapterStart}
                          onChange={(event) => setChapterStart(event.target.value)}
                          aria-label="From chapter"
                          className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                        />
                      </LabeledField>
                      <LabeledField label="Through chapter" isDark={isDark}>
                        <input
                          type="number"
                          min="1"
                          value={chapterEnd}
                          onChange={(event) => setChapterEnd(event.target.value)}
                          aria-label="Through chapter"
                          className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                        />
                      </LabeledField>
                    </div>
                  ) : null}
                  <div className="grid gap-3 sm:grid-cols-1">
                    <LabeledField label="Window days" detail="Beta-read windows must stay between 3 and 7 days." isDark={isDark}>
                      <input
                        type="number"
                        min="3"
                        max="7"
                        value={windowDays}
                        onChange={(event) => setWindowDays(event.target.value)}
                        aria-label="Window days"
                        className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                    </LabeledField>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <LabeledField label="Progress %" isDark={isDark}>
                      <input
                        type="number"
                        min="1"
                        max="100"
                        value={requiredProgressPct}
                        onChange={(event) => setRequiredProgressPct(event.target.value)}
                        aria-label="Progress percent"
                        className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                    </LabeledField>
                    <LabeledField label="Comments" isDark={isDark}>
                      <input
                        type="number"
                        min="0"
                        value={requiredCommentCount}
                        onChange={(event) => setRequiredCommentCount(event.target.value)}
                        aria-label="Required comments"
                        className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                    </LabeledField>
                    <LabeledField label="Review items" isDark={isDark}>
                      <input
                        type="number"
                        min="1"
                        value={requiredFeedbackItemCount}
                        onChange={(event) => setRequiredFeedbackItemCount(event.target.value)}
                        aria-label="Required review items"
                        className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                    </LabeledField>
                  </div>
                  <LabeledField label="Author questions" detail="Add up to 12 prompts, one per line, each up to 300 characters." isDark={isDark}>
                    <textarea
                      value={authorQuestionsText}
                      onChange={(event) => setAuthorQuestionsText(event.target.value)}
                      rows={5}
                      aria-label="Author questions"
                      className={`rounded-none border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    />
                  </LabeledField>
                </div>

                <button
                  type="button"
                  onClick={() => void createAssignment()}
                  disabled={saving || !readerEmail.trim() || !taskLabel.trim()}
                  className="app-button-primary mt-6 w-full"
                >
                  {saving ? "Saving..." : "Create beta read"}
                </button>
              </div> : null}

              <div className="order-1">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div><h2 className={`text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Assignments</h2><p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Choose an assignment to review its returned responses.</p></div>
                  <div className="flex items-center gap-3">
                    <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{authorAssignments.length} total</span>
                    <button type="button" onClick={() => { setCreateOpen(!createOpen); if (!createOpen) requestAnimationFrame(() => document.getElementById("new-assignment")?.querySelector("input")?.focus()) }} className="app-button-primary">{createOpen ? "Close form" : "New assignment"}</button>
                  </div>
                </div>
                <div className={`mt-5 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
                  {authorAssignments.length > 0 ? authorAssignments.map((assignment) => (
                    <button
                      type="button"
                      key={assignment.id}
                      aria-pressed={selectedAuthorAssignmentId === assignment.id}
                      onClick={() => void refreshAuthorDetail(assignment.id)}
                      className={`grid w-full gap-3 py-4 text-left transition-colors md:grid-cols-[minmax(0,1fr)_8rem_11rem_7rem] sm:items-center sm:gap-4 ${authorDetail?.assignment.id === assignment.id ? (isDark ? "text-white" : "bg-stone-50 text-stone-950") : (isDark ? "hover:bg-white/[0.03]" : "hover:bg-stone-50")}`}
                    >
                        <div className="min-w-0">
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{assignment.reader_email}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{assignment.task_label}</p>
                        </div>
                      <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{assignment.window_days} day window</span>
                      <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{assignment.feedback_item_count}/{assignment.required_feedback_item_count} responses · {assignment.comment_count}/{assignment.required_comment_count} comments</span>
                      <span className="text-xs font-medium">{assignment.status_label}</span>
                    </button>
                  )) : (
                    <p className={`py-5 text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No beta read assignments yet.</p>
                  )}
                </div>

                {workspace.authorSelectionMissing ? <p role="status" className="mt-4">The selected assignment is no longer available. Choose another assignment.</p> : null}
                {workspace.authorQuery.isLoading ? <p role="status" className="mt-4">Loading selected responses…</p> : null}
                {authorDetail ? (
                  <div className={`mt-7 border-t pt-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Selected assignment</p>
                        <p className="mt-1 text-sm">{authorDetail.assignment.reader_email}</p><p className="mt-2 text-sm">{authorDetail.assignment.scope_kind === "full_book" ? "Full manuscript" : `${authorDetail.assignment.section_label || "Chapters"}: ${authorDetail.assignment.chapter_start}–${authorDetail.assignment.chapter_end}`} · Deadline: {new Date(authorDetail.assignment.expires_at).toLocaleString()} · {authorDetail.assignment.status_label}</p>
                      </div>
                      {authorDetail.assignment.view_bucket === "active" || authorDetail.assignment.view_bucket === "scheduled" ? (
                        <button type="button" onClick={() => void revokeAssignment(authorDetail.assignment.id)} className="text-xs font-semibold text-rose-400">
                          Revoke
                        </button>
                      ) : null}
                    </div>

                    <div className={`mt-4 flex flex-wrap border-y py-3 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                      <StatPill label="Progress" value={`${authorDetail.assignment.progress_pct}%`} isDark={isDark} />
                      <StatPill label="Answers" value={`${authorDetail.feedback_summary.answer_count}`} isDark={isDark} />
                      <StatPill label="Confusing" value={`${authorDetail.feedback_summary.confusing_count}`} isDark={isDark} />
                      <StatPill label="Favorites" value={`${authorDetail.feedback_summary.favorite_count}`} isDark={isDark} />
                    </div>

                    {!authorDetail.feedback_items.length ? <p className="mt-5 text-sm">This reader has not returned structured feedback yet.</p> : null}
                    {authorDetail.feedback_items.length > 0 ? <div className="mt-6">
                      <h3 className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-stone-800"}`}>Responses</h3>
                      <div className={`mt-3 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
                        {authorDetail.feedback_items.map((item) => <article key={item.id} className="grid gap-2 py-4 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-4"><div className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{item.chapter_number ? `Chapter ${item.chapter_number}` : "Book-wide"}<br />{formatFeedbackKindLabel(item.kind)}</div><div>{item.question_prompt ? <p className="text-sm font-semibold">{item.question_prompt}</p> : null}{item.reaction ? <p className="mt-1 text-sm">Reaction: {formatFeedbackKindLabel(item.reaction)}</p> : null}{item.body ? <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{item.body}</p> : null}{item.anchor_text ? <p className={`mt-2 border-l-2 pl-3 text-sm italic ${isDark ? "border-white/15 text-slate-400" : "border-stone-300 text-stone-500"}`}>{item.anchor_text}</p> : null}</div></article>)}
                      </div>
                    </div> : null}

                    {<div className="mt-6">
                      <h3 className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-stone-800"}`}>Author questions</h3>
                      <div className={`mt-3 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
                        {authorDetail.author_questions.map((question) => (
                          <div key={question.id} className="py-3 text-sm">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <span>{question.prompt}</span>
                              <span className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{question.answer_count} answers</span>
                            </div>
                          </div>
                        ))}
                      </div>
                      <label htmlFor="additional-questions" className="mt-4 block text-sm">Additional questions</label>
                      <textarea id="additional-questions"
                        value={extraQuestionsText}
                        onChange={(event) => setExtraQuestionsText(event.target.value)}
                        rows={3}
                        aria-label="Additional author questions" disabled={!authorWritable}
                        className={`mt-3 w-full rounded-none border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                      <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Add up to 12 questions per request, each up to 300 characters. Drafts stay with this assignment.</p>
                      <button
                        type="button"
                        onClick={() => void appendQuestions()}
                        disabled={saving || !authorWritable || parseQuestionLines(extraQuestionsText).length === 0}
                        className={`mt-3 inline-flex h-10 items-center justify-center rounded-none px-4 text-sm font-semibold transition ${isDark ? "bg-white/10 text-slate-100 hover:bg-white/15 disabled:bg-white/5 disabled:text-slate-500" : "bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-500"}`}
                      >
                        Add questions
                      </button>
                    </div>}


                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          {!loading && !isAuthorView && readerDetail ? <ReaderFeedbackPanel workspace={workspace} isDark={isDark} /> : null}
          {!loading && !isAuthorView && !readerDetail && !workspace.readerQuery.isLoading && !workspace.readerQuery.isError ? <p className="py-6">No beta read is selected for this book. Choose an assignment above, or ask the author for an invitation.</p> : null}
          </fieldset>
        </main>
      </div>
    </div>

    {requirementsModal ? (
      <Dialog
        open
        onClose={() => setRequirementsModal(null)}
        eyebrow="Requirements not met"
        title="Complete these before submitting"
        size="sm"
      >
          <ul className="mt-5 space-y-3">
            {requirementsModal.map((issue) => (
              <li key={issue} className={`flex items-start gap-2.5 rounded-none border px-3.5 py-2.5 text-sm ${isDark ? "border-rose-500/20 bg-rose-500/10 text-rose-300" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
                <svg className="mt-0.5 h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <span>{issue}</span>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={() => setRequirementsModal(null)}
              className={`rounded-none px-5 py-2.5 text-sm font-semibold transition ${isDark ? "bg-slate-200 text-slate-950 hover:bg-white" : "bg-slate-900 text-white hover:bg-slate-800"}`}
            >
              Got it
            </button>
          </div>
      </Dialog>
    ) : null}

    </>
  )
}
