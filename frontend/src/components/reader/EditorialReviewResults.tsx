"use client"

import { useRef, useState, type ReactNode } from "react"
import type { Route } from "next"
import Link from "next/link"

import { intelligenceApi } from "@/lib/api/intelligence"
import type { EditorialContinuityIssue, EditorialGrammarIssue, EditorialInsertionOpportunity, EditorialReview, EditorialReviewPassage } from "@/types/intelligence"

type Props = {
  bookId: string
  chapterNumber: number | null
  editText: string
  editPassages: EditorialReviewPassage[]
  editResult: EditorialReview
  isDark: boolean
  onSaveNote: (title: string, body: string, chapterNumber: number | null) => Promise<void>
}

export function EditorialReviewResults({
  bookId,
  chapterNumber,
  editText,
  editPassages,
  editResult,
  isDark,
  onSaveNote,
}: Props) {
  return (
    <section className="min-w-0 space-y-7 [overflow-wrap:anywhere]">
      <div className={`border-y py-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <h3 className={`mb-2 text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>Overall verdict</h3>
        <p className={`text-base font-medium leading-7 ${isDark ? "text-slate-100" : "text-stone-900"}`}>{editResult.overall_verdict}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <QuietActionButton
            isDark={isDark}
            onClick={async () => {
              await onSaveNote(
                chapterNumber ? `Editorial Review - Chapter ${chapterNumber}` : "Editorial Review",
                editResult.overall_verdict,
                chapterNumber
              )
            }}
          >
            Save summary note
          </QuietActionButton>
          <QuietActionButton
            isDark={isDark}
            successMessage="Continuity report downloaded."
            onClick={async () => {
              const blob = await intelligenceApi.continuityReport(
                bookId,
                editText,
                "pdf",
                chapterNumber ?? undefined
              )
              const url = URL.createObjectURL(blob)
              const link = document.createElement("a")
              link.href = url
              link.download = "continuity-report.pdf"
              link.click()
              window.setTimeout(() => URL.revokeObjectURL(url), 1000)
            }}
          >
            Download continuity report
          </QuietActionButton>
        </div>
        <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">The download generates a separate continuity report for this reviewed passage.</p>
      </div>

      <div className={`border-y py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h3 className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>Thematic fit</h3>
          <span className={`text-xs font-medium capitalize ${editResult.thematic_fit.score === "strong" ? (isDark ? "text-teal-300" : "text-teal-800") : editResult.thematic_fit.score === "weak" ? (isDark ? "text-red-300" : "text-red-700") : (isDark ? "text-amber-300" : "text-amber-700")}`}>
            {editResult.thematic_fit.score}
          </span>
        </div>
        <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{editResult.thematic_fit.notes}</p>
      </div>

      {editResult.continuity_issues.length > 0 ? (
        <IssueList
          isDark={isDark}
          chapterNumber={chapterNumber}
          issues={editResult.continuity_issues}
          onSave={async (issue) => {
            await onSaveNote(
              `Continuity: ${issue.title}`.slice(0, 120),
              [
                `Continuity issue: ${issue.title}`,
                `Severity: ${issue.severity}`,
                `Type: ${issue.type.replace(/_/g, " ")}`,
                "",
                issue.description,
                issue.suggestion ? `Suggestion: ${issue.suggestion}` : "",
              ].filter(Boolean).join("\n"),
              chapterNumber
            )
          }}
        />
      ) : null}

      {(editResult.insertion_opportunities ?? []).length > 0 ? (
        <InsertionList
          bookId={bookId}
          isDark={isDark}
          items={editResult.insertion_opportunities ?? []}
          onSave={async (item) => {
            await onSaveNote(
              `Revision opportunity: ${item.title}`.slice(0, 120),
              [
                item.problem,
                "",
                `Add: ${item.what_to_add}`,
                `Why here: ${item.why_here}`,
                `Anchor: ${item.anchor_excerpt}`,
              ].join("\n"),
              item.target_chapter,
            )
          }}
        />
      ) : null}

      {editResult.grammar_issues.length > 0 ? (
        <GrammarList
          isDark={isDark}
          chapterNumber={chapterNumber}
          issues={editResult.grammar_issues}
          onSave={async (issue) => {
            await onSaveNote(
              `Grammar: ${issue.issue}`.slice(0, 120),
              [
                `Grammar issue: ${issue.issue}`,
                "",
                `Original: "${issue.original}"`,
                `Fix: "${issue.fix}"`,
              ].join("\n"),
              chapterNumber
            )
          }}
        />
      ) : null}

      {editResult.formatting_notes.length > 0 ? (
        <div>
          <h3 className={`mb-3 text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>
            Formatting notes
          </h3>
          <div className={`divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
            {editResult.formatting_notes.map((note, index) => (
              <div key={`${note}-${index}`} className="py-4">
                <div>
                  <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{note}</p>
                  <QuietActionButton
                    isDark={isDark}
                    className="mt-2"
                    onClick={() => onSaveNote("Formatting note", `Formatting note:\n${note}`, chapterNumber)}
                  >
                    Save note
                  </QuietActionButton>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {editPassages.length > 0 ? (
        <div>
          <h3 className={`mb-3 text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>
            Cross-referenced passages
          </h3>
          <div className={`divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
            {editPassages.map((passage, index) => (
              <div key={`${passage.chapter_num}-${index}`} className="py-4">
                <p className="mb-2 text-sm font-medium">
                  {Number.isInteger(passage.chapter_num) && passage.chapter_num > 0 ? <Link href={`/${bookId}/chapter/${passage.chapter_num}` as Route} className="underline underline-offset-4">Chapter {passage.chapter_num}{passage.chapter_title ? ` — ${passage.chapter_title}` : ""}</Link> : "Source chapter unavailable"}
                </p>
                <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{passage.excerpt}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {editPassages.length === 0 ? <p className="text-sm leading-6 text-[rgb(var(--muted-foreground))]">No cross-referenced passages were returned. Check important claims against your manuscript.</p> : null}

      {editResult.continuity_issues.length === 0 && editResult.grammar_issues.length === 0 ? (
        <div className={`border-y py-6 ${isDark ? "border-teal-500/30" : "border-teal-300"}`}>
          <p className="mb-2 text-sm font-semibold">Clear</p>
          <p className={`font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>No continuity or grammar issues found</p>
          <p className={`mt-1 text-xs ${isDark ? "text-teal-300" : "text-teal-700"}`}>No issues were identified in this pass. Check the source evidence before treating the passage as verified.</p>
        </div>
      ) : null}
    </section>
  )
}

function QuietActionButton({ children, className = "", isDark, onClick, successMessage = "Saved to Notes." }: {
  children: ReactNode
  className?: string
  isDark: boolean
  onClick: () => void | Promise<void>
  successMessage?: string
}) {
  const active = useRef(false)
  const [pending, setPending] = useState(false)
  const [feedback, setFeedback] = useState<{ error: boolean; message: string } | null>(null)
  const runAction = async () => {
    if (active.current) return
    active.current = true
    setPending(true)
    setFeedback(null)
    try {
      await onClick()
      setFeedback({ error: false, message: successMessage })
    } catch {
      setFeedback({ error: true, message: "Could not complete this action. Try again." })
    } finally {
      active.current = false
      setPending(false)
    }
  }
  return (
    <div className={className}>
      <button type="button" disabled={pending} aria-busy={pending} onClick={() => void runAction()}
        className={`min-h-10 py-2 text-sm font-medium underline underline-offset-4 transition disabled:opacity-60 ${isDark ? "text-slate-300" : "text-stone-700"}`}>
        {children}{pending ? "…" : ""}
      </button>
      {feedback ? <p role={feedback.error ? "alert" : "status"} className="text-sm leading-6 text-[rgb(var(--muted-foreground))]">{feedback.message}</p> : null}
    </div>
  )
}

function IssueList({
  chapterNumber,
  isDark,
  issues,
  onSave,
}: {
  chapterNumber: number | null
  isDark: boolean
  issues: EditorialContinuityIssue[]
  onSave: (issue: EditorialContinuityIssue) => Promise<void>
}) {
  return (
    <div>
      <h3 className={`mb-3 text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>
        Continuity issues ({issues.length})
      </h3>
      <div className={`divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
        {issues.map((issue, index) => (
          <div key={`${issue.title}-${index}`} className={`border-l-2 py-4 pl-4 ${
            issue.severity === "critical"
              ? "border-red-500"
              : issue.severity === "moderate"
                ? "border-amber-500"
                : isDark ? "border-slate-600" : "border-stone-300"
          }`}>
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
              <span className={`font-medium capitalize ${isDark ? "text-slate-300" : "text-stone-600"}`}>{issue.severity}</span>
              <span className={isDark ? "text-slate-600" : "text-stone-300"}>·</span>
              <span className={`capitalize ${isDark ? "text-slate-400" : "text-stone-600"}`}>{issue.type.replace(/_/g, " ")}</span>
              <QuietActionButton isDark={isDark} className="ml-auto" onClick={() => onSave(issue)}>
                Save note{chapterNumber ? ` (Ch. ${chapterNumber})` : ""}
              </QuietActionButton>
            </div>
            <p className={`mb-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{issue.title}</p>
            <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{issue.description}</p>
            {issue.suggestion ? (
              <p className={`mt-2 text-sm font-medium leading-6 ${isDark ? "text-violet-200" : "text-violet-700"}`}>
                Suggestion: {issue.suggestion}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}

function GrammarList({
  chapterNumber,
  isDark,
  issues,
  onSave,
}: {
  chapterNumber: number | null
  isDark: boolean
  issues: EditorialGrammarIssue[]
  onSave: (issue: EditorialGrammarIssue) => Promise<void>
}) {
  return (
    <div>
      <h3 className={`mb-3 text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>
        Grammar & spelling ({issues.length})
      </h3>
      <div className={`divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
        {issues.map((issue, index) => (
          <div key={`${issue.issue}-${index}`} className="py-4">
            <p className={`mb-1 text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-600"}`}>{issue.issue}</p>
            <p className={`mb-1 text-sm line-through ${isDark ? "text-slate-300" : "text-stone-600"}`}>"{issue.original}"</p>
            <p className={`text-sm font-medium ${isDark ? "text-teal-300" : "text-teal-700"}`}>Fix: "{issue.fix}"</p>
            <QuietActionButton isDark={isDark} className="mt-3" onClick={() => onSave(issue)}>
              Save note{chapterNumber ? ` (Ch. ${chapterNumber})` : ""}
            </QuietActionButton>
          </div>
        ))}
      </div>
    </div>
  )
}

function InsertionList({
  bookId,
  isDark,
  items,
  onSave,
}: {
  bookId: string
  isDark: boolean
  items: EditorialInsertionOpportunity[]
  onSave: (item: EditorialInsertionOpportunity) => Promise<void>
}) {
  return (
    <div>
      <h3 className={`mb-3 text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>Revision opportunities ({items.length})</h3>
      <div className={`divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
        {items.map((item, index) => (
          <article key={`${item.title}-${index}`} className="py-4">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className={`capitalize ${isDark ? "text-slate-400" : "text-stone-600"}`}>{item.purpose.replaceAll("_", " ")}</span>
              <span className={isDark ? "text-slate-600" : "text-stone-300"}>·</span>
              <Link href={`/${bookId}/chapter/${item.target_chapter}` as Route} className={`font-medium underline decoration-transparent underline-offset-4 hover:decoration-current ${isDark ? "text-teal-300" : "text-teal-800"}`}>
                Chapter {item.target_chapter}{item.target_chapter_title ? ` — ${item.target_chapter_title}` : ""}
              </Link>
              <QuietActionButton isDark={isDark} className="ml-auto" onClick={() => onSave(item)}>Save note</QuietActionButton>
            </div>
            <p className={`mt-2 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{item.title}</p>
            <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{item.problem}</p>
            <p className={`mt-3 text-sm leading-6 ${isDark ? "text-teal-200" : "text-teal-800"}`}><span className="font-medium">Suggested addition:</span> {item.what_to_add}</p>
            <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{item.why_here}</p>
            {item.anchor_excerpt ? <blockquote className="mt-3 border-l-2 border-[rgb(var(--border))] pl-3 text-sm leading-6"><span className="font-medium">Passage anchor: </span>{item.anchor_excerpt}</blockquote> : null}
          </article>
        ))}
      </div>
    </div>
  )
}
