"use client"

import type { ReactNode } from "react"

import { intelligenceApi } from "@/lib/api/intelligence"
import type { EditorialContinuityIssue, EditorialGrammarIssue, EditorialReview, EditorialReviewPassage } from "@/types/intelligence"

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
    <section className="space-y-5">
      <div className={`rounded-[1.5rem] border px-6 py-5 ${isDark ? "border-violet-400/20 bg-violet-500/10" : "border-violet-200 bg-violet-50"}`}>
        <p className={`mb-2 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-violet-200" : "text-violet-700"}`}>Overall verdict</p>
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
              URL.revokeObjectURL(url)
            }}
          >
            Download continuity report
          </QuietActionButton>
        </div>
      </div>

      <div className={`rounded-[1.5rem] border px-5 py-4 ${
        editResult.thematic_fit.score === "strong"
          ? isDark ? "border-teal-500/25 bg-teal-500/8" : "border-teal-200 bg-teal-50"
          : editResult.thematic_fit.score === "weak"
            ? isDark ? "border-red-500/25 bg-red-500/8" : "border-red-200 bg-red-50"
            : isDark ? "border-amber-500/25 bg-amber-500/8" : "border-amber-200 bg-amber-50"
      }`}>
        <div className="mb-2 flex items-center gap-2">
          <p className={`text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-300" : "text-stone-500"}`}>Thematic fit</p>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] ${
            editResult.thematic_fit.score === "strong"
              ? isDark ? "bg-teal-500/20 text-teal-300" : "bg-teal-100 text-teal-700"
              : editResult.thematic_fit.score === "weak"
                ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                : isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
          }`}>
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
          <p className={`mb-3 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-300" : "text-stone-500"}`}>
            Formatting notes
          </p>
          <div className={`space-y-3 rounded-[1.2rem] border px-5 py-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/80"}`}>
            {editResult.formatting_notes.map((note, index) => (
              <div key={`${note}-${index}`} className="flex items-start gap-3">
                <span className={`mt-[0.35rem] h-1.5 w-1.5 rounded-full ${isDark ? "bg-slate-500" : "bg-stone-400"}`} />
                <div className="flex-1">
                  <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{note}</p>
                  <QuietActionButton
                    isDark={isDark}
                    className="mt-2"
                    onClick={() => void onSaveNote("Formatting note", `Formatting note:\n${note}`, chapterNumber)}
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
          <p className={`mb-3 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Cross-referenced passages
          </p>
          <div className="grid gap-3 lg:grid-cols-2">
            {editPassages.map((passage, index) => (
              <div key={`${passage.chapter_num}-${index}`} className={`rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/80"}`}>
                <p className={`mb-2 text-[10px] font-bold uppercase tracking-[0.22em] ${isDark ? "text-violet-200" : "text-violet-700"}`}>
                  Ch. {passage.chapter_num}{passage.chapter_title ? `: ${passage.chapter_title}` : ""}
                </p>
                <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{passage.excerpt}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {editResult.continuity_issues.length === 0 && editResult.grammar_issues.length === 0 ? (
        <div className={`rounded-[1.5rem] border p-6 text-center ${isDark ? "border-teal-500/20 bg-teal-500/8" : "border-teal-200 bg-teal-50"}`}>
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.24em]">Clear</p>
          <p className={`font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>No continuity or grammar issues found</p>
          <p className={`mt-1 text-xs ${isDark ? "text-teal-300" : "text-teal-700"}`}>The passage looks consistent with the existing manuscript context.</p>
        </div>
      ) : null}
    </section>
  )
}

function QuietActionButton({
  children,
  className = "",
  isDark,
  onClick,
}: {
  children: ReactNode
  className?: string
  isDark: boolean
  onClick: () => void | Promise<void>
}) {
  return (
    <button
      type="button"
      onClick={() => void onClick()}
      className={`rounded-[0.85rem] border px-4 py-2 text-xs font-semibold transition ${
        isDark ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
      } ${className}`}
    >
      {children}
    </button>
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
      <p className={`mb-3 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>
        Continuity issues ({issues.length})
      </p>
      <div className="space-y-3">
        {issues.map((issue, index) => (
          <div key={`${issue.title}-${index}`} className={`rounded-[1.2rem] border px-5 py-4 ${
            issue.severity === "critical"
              ? isDark ? "border-red-500/30 bg-red-500/10" : "border-red-200 bg-red-50"
              : issue.severity === "moderate"
                ? isDark ? "border-amber-500/30 bg-amber-500/8" : "border-amber-200 bg-amber-50"
                : isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/80"
          }`}>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.22em] ${
                issue.severity === "critical"
                  ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                  : issue.severity === "moderate"
                    ? isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
                    : isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"
              }`}>
                {issue.severity}
              </span>
              <span className={`text-[10px] font-medium uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                {issue.type.replace(/_/g, " ")}
              </span>
              <QuietActionButton isDark={isDark} className="ml-auto" onClick={() => onSave(issue)}>
                Save note{chapterNumber ? ` (Ch. ${chapterNumber})` : ""}
              </QuietActionButton>
            </div>
            <p className={`mb-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{issue.title}</p>
            <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{issue.description}</p>
            {issue.suggestion ? (
              <p className={`mt-2 text-xs font-medium leading-5 ${isDark ? "text-violet-200" : "text-violet-700"}`}>
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
      <p className={`mb-3 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-300" : "text-stone-500"}`}>
        Grammar & spelling ({issues.length})
      </p>
      <div className="space-y-2.5">
        {issues.map((issue, index) => (
          <div key={`${issue.issue}-${index}`} className={`rounded-[1.1rem] border px-4 py-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/80"}`}>
            <p className={`mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>{issue.issue}</p>
            <p className={`mb-1 text-sm line-through opacity-70 ${isDark ? "text-slate-300" : "text-stone-600"}`}>"{issue.original}"</p>
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
