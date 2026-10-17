import { FEEDBACK_KIND_OPTIONS, FINAL_RATING_OPTIONS, LabeledField, StatPill } from "./betaFeedbackPage.components"
import { formatFeedbackKindLabel } from "@/lib/utils/betaRead"
import { reviewRequirements } from "./betaFeedbackPage.helpers"
import type { BetaFeedbackWorkspace } from "./betaFeedbackPage.state"

export function ReaderFeedbackPanel({ workspace, isDark }: { workspace: BetaFeedbackWorkspace; isDark: boolean }) {
  const { readerDetail, saving, readerWritable, feedbackKind, setFeedbackKind, feedbackChapter, setFeedbackChapter, feedbackReaction, setFeedbackReaction, feedbackAnchor, setFeedbackAnchor, feedbackBody, setFeedbackBody, selectedQuestionId, setSelectedQuestionId, finalReview, setFinalReview, finalRating, setFinalRating, startAssignment, createFeedbackItem, deleteFeedbackItem, submitReview } = workspace
  const activeFeedbackKind = FEEDBACK_KIND_OPTIONS.find((option) => option.value === feedbackKind)
  return <>
          {readerDetail ? (
            <section className="grid gap-6 lg:grid-cols-2">
              <div className={`border-y py-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Your beta read</h2>
                    <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>{readerDetail.assignment.task_label}</p>
                  </div>
                  <span className={`rounded-none px-2.5 py-1 text-3xs font-semibold ${readerDetail.assignment.submission_allowed ? "bg-emerald-500/10 text-emerald-400" : "bg-sky-500/10 text-sky-400"}`}>
                    {readerDetail.assignment.status_label}
                  </span>
                </div>

                <p className="mt-4 text-sm">Scope: {readerDetail.assignment.scope_kind === "full_book" ? "Full manuscript" : `Chapters ${readerDetail.assignment.chapter_start}–${readerDetail.assignment.chapter_end}`} · Deadline: {new Date(readerDetail.assignment.expires_at).toLocaleString()}</p><div className="mt-5 flex flex-wrap gap-y-3">
                  <StatPill label="Window" value={`${readerDetail.assignment.window_days} days`} isDark={isDark} />
                  <StatPill label="Progress" value={`${readerDetail.assignment.progress_pct}%`} isDark={isDark} />
                  <StatPill label="Comments" value={`${readerDetail.assignment.comment_count}/${readerDetail.assignment.required_comment_count}`} isDark={isDark} />
                  <StatPill label="Review items" value={`${readerDetail.assignment.feedback_item_count}/${readerDetail.assignment.required_feedback_item_count}`} isDark={isDark} />
                </div>

                <div className={`mt-5 rounded-none border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Author questions</p>
                  <div className="mt-3 space-y-2">
                    {readerDetail.author_questions.length > 0 ? readerDetail.author_questions.map((question) => (
                      <div key={question.id} className={`rounded-none border px-3 py-2 text-sm ${isDark ? "border-white/[0.06] bg-white/[0.02] text-slate-200" : "border-slate-200 bg-white text-slate-700"}`}>
                        {question.prompt}
                      </div>
                    )) : (
                      <p className={`text-sm ${isDark ? "text-slate-500" : "text-slate-500"}`}>No direct author questions on this assignment.</p>
                    )}
                  </div>
                </div>

                {!readerWritable ? <p role="status" className="mt-5 border-l-2 pl-3 text-sm">This assignment is read-only in its current state or with your current permissions. Refresh to check for updates.</p> : null}
                <fieldset disabled={saving || !readerWritable} className="mt-5 min-w-0 border-0 p-0">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Add structured feedback</h3>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{activeFeedbackKind?.detail}</p>
                    </div>
                    {readerDetail.assignment.state === "active" ? (
                      <button type="button" onClick={() => void startAssignment()} className={`rounded-none px-3 py-2 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-slate-900 text-white"}`}>
                        Start
                      </button>
                    ) : null}
                  </div>
                  <div className="mt-4 grid gap-3">
                    <label className="text-sm" htmlFor="feedback-kind">Feedback type</label>
                    <select id="feedback-kind" aria-label="Feedback type"
                      value={feedbackKind}
                      onChange={(event) => setFeedbackKind(event.target.value)}
                      className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                    >
                      {FEEDBACK_KIND_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <LabeledField label="Chapter number" detail="Choose a chapter within your assigned scope. Only answers to author questions may be book-wide." isDark={isDark}>
                        <input
                          type="number"
                          min="1"
                          value={feedbackChapter}
                          onChange={(event) => setFeedbackChapter(event.target.value)}
                          aria-label="Feedback chapter number"
                          className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                        />
                      </LabeledField>
                      <LabeledField label="Linked question" isDark={isDark}>
                        <select
                          value={selectedQuestionId}
                          onChange={(event) => setSelectedQuestionId(event.target.value)}
                          aria-label="Linked author question"
                          className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                        >
                          <option value="">No linked author question</option>
                          {readerDetail.author_questions.map((question) => (
                            <option key={question.id} value={question.id}>{question.prompt}</option>
                          ))}
                        </select>
                      </LabeledField>
                    </div>
                    <LabeledField label="Reaction label" detail="Use this for quick scene reactions, if this item needs one." isDark={isDark}>
                      <input
                        value={feedbackReaction}
                        onChange={(event) => setFeedbackReaction(event.target.value)}
                        aria-label="Reaction label" maxLength={64}
                        className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                      />
                    </LabeledField>
                    <LabeledField label="Anchor text" detail="Quote the passage or marker this feedback refers to." isDark={isDark}>
                      <input
                        value={feedbackAnchor}
                        onChange={(event) => setFeedbackAnchor(event.target.value)}
                        aria-label="Anchor text" maxLength={500}
                        className={`h-11 rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                      />
                    </LabeledField>
                    <LabeledField label="Feedback body" detail="Write what landed, dragged, confused you, or directly answers the author." isDark={isDark}>
                      <textarea
                        value={feedbackBody}
                        onChange={(event) => setFeedbackBody(event.target.value)}
                        rows={5}
                        aria-label="Feedback body" maxLength={10000}
                        className={`rounded-none border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                      />
                    </LabeledField>
                    <button
                      type="button"
                      onClick={() => void createFeedbackItem()}
                      disabled={saving}
                      className="app-button-primary"
                    >
                      Save feedback item
                    </button>
                  </div>
                </fieldset>
              </div>

              <div className={`border-y py-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Review trail</h2>
                <div className="mt-5 flex flex-wrap gap-y-3">
                  <StatPill label="Answers" value={`${readerDetail.feedback_summary.answer_count}`} isDark={isDark} />
                  <StatPill label="Confusing" value={`${readerDetail.feedback_summary.confusing_count}`} isDark={isDark} />
                  <StatPill label="Boring" value={`${readerDetail.feedback_summary.boring_count}`} isDark={isDark} />
                  <StatPill label="Favorites" value={`${readerDetail.feedback_summary.favorite_count}`} isDark={isDark} />
                </div>
                <div className="mt-5 space-y-3">
                  {readerDetail.feedback_items.length > 0 ? readerDetail.feedback_items.map((item) => (
                    <div key={item.id} className={`rounded-none border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{formatFeedbackKindLabel(item.kind)}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                            {item.chapter_number ? `Chapter ${item.chapter_number}` : "Book-wide"}{item.scene_title ? ` / ${item.scene_title}` : ""}
                          </p>
                        </div>
                        {readerWritable ? (
                          <button type="button" disabled={saving} aria-label={`Remove feedback: ${item.body || item.anchor_text || item.id}`} onClick={() => void deleteFeedbackItem(item.id)} className="text-xs font-semibold text-rose-400">
                            Remove
                          </button>
                        ) : null}
                      </div>
                      {item.question_prompt ? <p className={`mt-3 text-xs font-semibold ${isDark ? "text-amber-300" : "text-amber-700"}`}>Q: {item.question_prompt}</p> : null}
                      {item.reaction ? <p className={`mt-3 text-xs font-semibold ${isDark ? "text-sky-300" : "text-sky-700"}`}>Reaction: {formatFeedbackKindLabel(item.reaction)}</p> : null}
                      {item.anchor_text ? <p className={`mt-3 text-sm italic ${isDark ? "text-slate-300" : "text-slate-700"}`}>{item.anchor_text}</p> : null}
                      {item.body ? <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{item.body}</p> : null}
                    </div>
                  )) : (
                    <div className={`rounded-none border border-dashed p-5 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                      No structured feedback saved yet.
                    </div>
                  )}
                </div>

                <div className={`mt-5 rounded-none border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Final review</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    Complete the reading, comment, feedback, and question requirements, then submit your final review and a rating from 1 to 5 in half-point steps. Submission closes this feedback pass.
                  </p>
                  <label className="mt-4 block text-sm" htmlFor="final-rating">Final rating</label>
                  <select id="final-rating"
                    aria-label="Final rating" disabled={saving || !readerWritable}
                    value={readerWritable ? finalRating : (readerDetail.assignment.final_rating?.toString() ?? "")}
                    onChange={(event) => setFinalRating(event.target.value)}
                    className={`mt-4 h-11 w-full rounded-none border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 focus:border-emerald-400" : "border-slate-200 bg-white text-slate-900 focus:border-emerald-400"}`}
                  >
                    {!readerWritable && readerDetail.assignment.final_rating == null ? <option value="">No saved rating available</option> : null}
                    {FINAL_RATING_OPTIONS.map((rating) => (
                      <option key={rating} value={rating.toString()}>{`${rating.toFixed(1)} / 5`}</option>
                    ))}
                  </select>
                  {readerWritable && reviewRequirements(readerDetail).length > 0 ? <div className="mt-4 text-sm"><h3 className="font-semibold">Before submitting</h3><ul className="mt-2 list-disc space-y-1 pl-5">{reviewRequirements(readerDetail).map((requirement) => <li key={requirement}>{requirement}</li>)}</ul></div> : null}
                  <label className="mt-4 block text-sm" htmlFor="final-review">Final review text</label>
                  <textarea id="final-review"
                    value={finalReview}
                    onChange={(event) => setFinalReview(event.target.value)}
                    rows={6}
                    aria-label="Final review" disabled={saving || !readerWritable} maxLength={20000}
                    className={`mt-4 w-full rounded-none border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 focus:border-emerald-400" : "border-slate-200 bg-white text-slate-900 focus:border-emerald-400"}`}
                  />
                  <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Summarize what hooked you, what felt predictable, what confused you, and who you cared about most.</p>
                  <button
                    type="button"
                    onClick={() => void submitReview()}
                    disabled={saving || !readerWritable || !finalReview.trim()}
                    className="app-button-primary mt-4 w-full"
                  >
                    Submit review
                  </button>
                </div>
              </div>
            </section>
          ) : null}

</>
}
