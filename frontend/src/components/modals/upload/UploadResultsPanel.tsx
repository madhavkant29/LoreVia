"use client"

import { intelligenceApi } from "@/lib/api/intelligence"
import type { ChapterConsistencyReport } from "@/types/book"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"
import { PostImportChecklist, ReportList } from "./UploadWizardPanels"

type ReviewTarget = { bookId: string; chapterNum?: number; text: string }

type Props = {
  isDark: boolean
  chapterReports: ChapterConsistencyReport[]
  storyUnitLabel: string
  storyUnitLabelTitle: string
  postImportReview: EditorialReview | null
  reportReady: ReviewTarget | null
  postImportSynopsis: ManuscriptSynopsis | null
  postImportPassages: EditorialReviewPassage[]
  postImportThreads: PlotThread[]
  postImportSuggestions: AdvisorSuggestion[]
}

export function UploadResultsPanel({
  isDark, chapterReports, storyUnitLabel, storyUnitLabelTitle, postImportReview, reportReady,
  postImportSynopsis, postImportPassages, postImportThreads, postImportSuggestions,
}: Props) {
  return (
    <>
          {chapterReports.length > 0 ? (
            <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-50"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>{`${storyUnitLabelTitle} consistency report`}</p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{`Generated from the latest import so you can review the ${storyUnitLabel} in under 30 seconds.`}</p>
                </div>
              </div>

              <div className="mt-4 space-y-4">
                {chapterReports.map((report) => (
                  <div key={`${report.chapter_number}-${report.chapter_title ?? "untitled"}`} className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-white bg-white"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                          {storyUnitLabelTitle} {report.chapter_number}{report.chapter_title ? ` - ${report.chapter_title}` : ""}
                        </p>
                        <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{report.summary}</p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 xl:grid-cols-2">
                      <div className="space-y-3">
                        <ReportList
                          title="New characters"
                          emptyLabel="No new characters detected."
                          items={report.new_characters.map((character) => {
                            const details = [character.role, character.arc_summary].filter(Boolean).join(" - ")
                            return details ? `${character.name} (${details})` : character.name
                          })}
                          isDark={isDark}
                        />
                        <ReportList
                          title="Relationship changes"
                          emptyLabel="No new relationship shifts were recorded."
                          items={report.relationship_changes}
                          isDark={isDark}
                        />
                      </div>

                      <div className="space-y-3">
                        <ReportList
                          title="Plot threads opened"
                          emptyLabel="No new plot threads opened in this chapter."
                          items={report.plot_threads_opened}
                          isDark={isDark}
                        />
                        <ReportList
                          title="Plot threads resolved"
                          emptyLabel="No plot threads resolved in this chapter."
                          items={report.plot_threads_resolved}
                          isDark={isDark}
                        />
                        <ReportList
                          title="Continuity flags"
                          emptyLabel="No immediate continuity flags were found."
                          items={report.continuity_flags}
                          isDark={isDark}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {(chapterReports.length > 0 || postImportReview) ? (
            <PostImportChecklist isDark={isDark} hasReview={Boolean(postImportReview)} hasReports={chapterReports.length > 0} />
          ) : null}

          {postImportReview ? (
            <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-50"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Immediate continuity review</p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{postImportReview.overall_verdict}</p>
                </div>
                {reportReady ? (
                  <button
                    type="button"
                    onClick={async () => {
                      const blob = await intelligenceApi.continuityReport(reportReady.bookId, reportReady.text, "pdf", reportReady.chapterNum)
                      const url = URL.createObjectURL(blob)
                      const link = document.createElement("a")
                      link.href = url
                      link.download = "continuity-report.pdf"
                      link.click()
                      URL.revokeObjectURL(url)
                    }}
                    className={`rounded-full border px-4 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-100"}`}
                  >
                    Download continuity report
                  </button>
                ) : null}
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                <div className="space-y-3">
                  {postImportSynopsis ? (
                    <div>
                      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Spoiler-light synopsis</p>
                      <div className={`rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                        <p>{postImportSynopsis.synopsis}</p>
                        {postImportSynopsis.focus_points.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {postImportSynopsis.focus_points.map((point) => (
                              <span key={point} className={`rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-700"}`}>{point}</span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                  <div>
                    <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Broader editorial continuity review</p>
                    <p className={`mb-3 text-xs leading-5 ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                      These come from LoreVia&apos;s wider story-context review. Fresh chapter-specific flags appear above in the chapter report.
                    </p>
                    {postImportReview.continuity_issues.length > 0 ? postImportReview.continuity_issues.map((issue, index) => (
                      <div key={`${issue.title}-${index}`} className={`mb-2 rounded-lg border px-3 py-3 text-sm ${isDark ? "border-amber-500/20 bg-amber-500/10 text-slate-200" : "border-amber-200 bg-amber-50 text-stone-700"}`}>
                        <p className="font-semibold">{issue.title}</p>
                        <p className="mt-1 text-xs opacity-80">{issue.description}</p>
                        {issue.suggestion ? <p className="mt-2 text-xs font-medium opacity-90">{issue.suggestion}</p> : null}
                      </div>
                    )) : (
                      <p className={`text-sm ${isDark ? "text-teal-300" : "text-teal-700"}`}>No continuity issues found in this upload.</p>
                    )}
                  </div>

                  {postImportReview.insertion_opportunities.length > 0 ? (
                    <div>
                      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Best insertion opportunities</p>
                      <div className="space-y-2">
                        {postImportReview.insertion_opportunities.map((item, index) => (
                          <div key={`${item.title}-${index}`} className={`rounded-lg border px-3 py-3 text-sm ${isDark ? "border-teal-500/20 bg-teal-500/10 text-slate-200" : "border-teal-200 bg-teal-50 text-stone-700"}`}>
                            <p className="font-semibold">{item.title}</p>
                            <p className="mt-1 text-xs opacity-80">Chapter {item.target_chapter}{item.target_chapter_title ? ` - ${item.target_chapter_title}` : ""}</p>
                            <p className="mt-2 text-xs leading-5 opacity-80">{item.problem}</p>
                            <p className="mt-2 text-xs font-medium opacity-95">Add: {item.what_to_add}</p>
                            <p className="mt-2 text-xs opacity-80">{item.why_here}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {postImportPassages.length > 0 ? (
                    <div>
                      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Cross-referenced passages</p>
                      <div className="space-y-2">
                        {postImportPassages.map((passage, index) => (
                          <div key={`${passage.chapter_num}-${index}`} className={`rounded-lg border px-3 py-3 text-xs leading-5 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                            <p className={`mb-1 font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>Chapter {passage.chapter_num}{passage.chapter_title ? ` - ${passage.chapter_title}` : ""}</p>
                            <p>{passage.excerpt}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="space-y-3">
                  <div>
                    <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Forgotten threads</p>
                    {postImportThreads.length > 0 ? postImportThreads.map((thread) => (
                      <div key={thread.id} className={`mb-2 rounded-lg border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                        <p className="font-semibold">{thread.title}</p>
                        <p className="mt-1 text-xs opacity-80">Introduced in chapter {thread.introduced_at ?? "?"} - {thread.status}</p>
                      </div>
                    )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No unresolved thread warnings loaded.</p>}
                  </div>

                  <div>
                    <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Improvement prompts</p>
                    {postImportSuggestions.length > 0 ? postImportSuggestions.map((item) => (
                      <div key={item.id} className={`mb-2 rounded-lg border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                        <p className="font-semibold">{item.title}</p>
                        <p className="mt-1 text-xs opacity-80">{item.description}</p>
                      </div>
                    )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No follow-up prompts were generated.</p>}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
    </>
  )
}
