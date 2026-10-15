"use client"

import { useId, useState } from "react"

import { betaReaderScopeLabel, matchesBetaReaderFilters, matchesBetaReaderTermFilters } from "@/lib/utils/aiBetaReader"
import type { BetaReaderFinding, BetaReaderReport, BetaReaderRevisionCandidate } from "@/types/intelligence"
import { EvidenceLinks, FindingCard } from "./reportComponents"

type ResultTab = "reader" | "repetition" | "voices" | "revisions"

const TAB_OPTIONS: Array<{ id: ResultTab; label: string }> = [
  { id: "reader", label: "Reader report" },
  { id: "repetition", label: "Overused language" },
  { id: "voices", label: "Character voices" },
  { id: "revisions", label: "Revision priorities" },
]

export function BetaReaderReportView({
  bookId,
  report,
  canCreateTask,
  creatingTaskId,
  savingNote = false,
  onSaveReport,
  onSaveFinding,
  onCreateTask,
}: {
  bookId: string
  report: BetaReaderReport
  canCreateTask: boolean
  creatingTaskId: string | null
  savingNote?: boolean
  onSaveReport: () => void
  onSaveFinding: (item: BetaReaderFinding | BetaReaderRevisionCandidate) => void
  onCreateTask: (candidate: BetaReaderRevisionCandidate) => void
}) {
  const tabId = useId()
  const [activeTab, setActiveTab] = useState<ResultTab>("reader")
  const [chapterFilter, setChapterFilter] = useState("all")
  const [characterFilter, setCharacterFilter] = useState("all")
  const [severityFilter, setSeverityFilter] = useState("all")
  const [typeFilter, setTypeFilter] = useState("all")
  const scopeLabel = betaReaderScopeLabel(report.scope, report.coverage.requested_chapters)
  const filteredFindings = report.findings.filter((item) => matchesBetaReaderFilters(item, {
    chapter: chapterFilter,
    severity: severityFilter,
    findingType: typeFilter,
  }))
  const filteredCandidates = report.revision_candidates.filter((item) => matchesBetaReaderFilters(item, {
    chapter: chapterFilter,
    severity: severityFilter,
    findingType: typeFilter,
  }))
  const filteredTerms = report.overused_terms.filter((item) => matchesBetaReaderTermFilters(item, {
    chapter: chapterFilter,
    findingType: typeFilter,
  }))
  const filteredVoices = report.character_voices.filter(
    (item) => characterFilter === "all" || item.character_id === characterFilter,
  )
  const findingTypes = Array.from(new Set(activeTab === "repetition" ? report.overused_terms.map((item) => item.kind) : activeTab === "revisions" ? report.revision_candidates.map((item) => item.category) : report.findings.map((item) => item.category)))
  const selectTab = (tab: ResultTab) => {
    setActiveTab(tab)
    setTypeFilter("all")
  }
  const count = activeTab === "reader" ? filteredFindings.length : activeTab === "revisions" ? filteredCandidates.length : activeTab === "repetition" ? filteredTerms.length : filteredVoices.length
  const hasFilters = chapterFilter !== "all" || characterFilter !== "all" || severityFilter !== "all" || typeFilter !== "all"
  const showChapterFilter = activeTab !== "voices"
  const showCharacterFilter = activeTab === "voices"
  const showSeverityFilter = activeTab === "reader" || activeTab === "revisions"
  const showTypeFilter = activeTab === "reader" || activeTab === "repetition" || activeTab === "revisions"

  return (
    <div className="min-w-0 [overflow-wrap:anywhere]">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-[rgb(var(--border))] pb-5">
        <div>
          <p className="text-sm font-medium text-[rgb(var(--muted-foreground))]">{scopeLabel}</p>
          <h2 data-beta-step-heading tabIndex={-1} className="mt-1 text-2xl font-semibold">Reader report</h2>
          <p className="app-copy mt-2">
            {report.coverage.word_count.toLocaleString()} words · {report.coverage.analyzed_chapters.length ? `${report.coverage.analyzed_chapters.length} chapter${report.coverage.analyzed_chapters.length === 1 ? "" : "s"} analyzed` : "Pasted passage"}
          </p>
        </div>
        <button type="button" onClick={onSaveReport} disabled={savingNote} aria-busy={savingNote} className="app-button-secondary">Save to notes</button>
      </header>

      {report.coverage.missing_chapters.length ? <p className="mt-3 border-l-2 border-amber-500 pl-3 text-sm">Not analyzed: {report.coverage.missing_chapters.map((chapter) => `Chapter ${chapter}`).join(", ")}. This report covers the available text only.</p> : null}

      {report.is_stale ? (
        <p className="mt-4 border-l-2 border-amber-500 py-1 pl-3 text-sm text-[rgb(var(--muted-foreground))]" role="status">
          This report is from an earlier manuscript version. It remains available for reference; run again for current results.
        </p>
      ) : null}
      {report.warnings.length ? (
        <div className="mt-4 border-l-2 border-amber-500 py-1 pl-3 text-sm text-amber-700">
          {report.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-2 gap-x-3 border-b border-[rgb(var(--border))] xl:flex xl:flex-wrap xl:gap-x-5" role="tablist" aria-label="AI Beta Reader results">
        {TAB_OPTIONS.map((tab, index) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`${tabId}-${tab.id}`}
            aria-controls={`${tabId}-panel`}
            tabIndex={activeTab === tab.id ? 0 : -1}
            aria-selected={activeTab === tab.id}
            onClick={() => selectTab(tab.id)}
            onKeyDown={(event) => {
              const next = event.key === "Home" ? 0 : event.key === "End" ? TAB_OPTIONS.length - 1 : event.key === "ArrowRight" ? (index + 1) % TAB_OPTIONS.length : event.key === "ArrowLeft" ? (index + TAB_OPTIONS.length - 1) % TAB_OPTIONS.length : null
              if (next === null) return
              event.preventDefault()
              selectTab(TAB_OPTIONS[next].id)
              document.getElementById(`${tabId}-${TAB_OPTIONS[next].id}`)?.focus()
            }}
            className={`min-h-11 border-b-2 px-0 py-3 text-left text-sm font-semibold ${activeTab === tab.id ? "border-[rgb(var(--accent))] text-[rgb(var(--foreground))]" : "border-transparent text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]"}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`${tabId}-panel`} aria-labelledby={`${tabId}-${activeTab}`} tabIndex={0}>
      {(showChapterFilter || showCharacterFilter || showSeverityFilter || showTypeFilter) ? (
        <div className="mt-4 flex flex-wrap gap-3 border-b border-[rgb(var(--border))] pb-4">
          {showChapterFilter ? (
            <label className="min-w-40 max-w-full flex-1 text-sm">Chapter
              <select value={chapterFilter} onChange={(event) => setChapterFilter(event.target.value)} className="app-input mt-1 w-full">
                <option value="all">All chapters</option>
                {report.coverage.analyzed_chapters.map((chapter) => <option key={chapter} value={chapter}>Chapter {chapter}</option>)}
              </select>
            </label>
          ) : null}
          {showCharacterFilter ? (
            <label className="min-w-40 flex-1 text-sm">Character
              <select value={characterFilter} onChange={(event) => setCharacterFilter(event.target.value)} className="app-input mt-1 w-full">
                <option value="all">All characters</option>
                {report.character_voices.map((voice) => <option key={voice.character_id} value={voice.character_id}>{voice.character_name}</option>)}
              </select>
            </label>
          ) : null}
          {showSeverityFilter ? (
            <label className="min-w-40 flex-1 text-sm">Severity
              <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} className="app-input mt-1 w-full">
                <option value="all">All severities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
              </select>
            </label>
          ) : null}
          {showTypeFilter ? (
            <label className="min-w-40 flex-1 text-sm">Finding type
              <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="app-input mt-1 w-full">
                <option value="all">All types</option>
                {findingTypes.map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}
              </select>
            </label>
          ) : null}
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-[rgb(var(--muted-foreground))]"><p role="status">{count} {activeTab === "voices" ? "voice comparisons" : activeTab === "repetition" ? "repeated terms" : (count === 1 ? "finding" : "findings")} shown{activeTab === "reader" ? ". Filters apply to findings below the report summary." : ""}</p>{hasFilters ? <button type="button" className="min-h-10 underline underline-offset-4" onClick={() => { setChapterFilter("all"); setCharacterFilter("all"); setSeverityFilter("all"); setTypeFilter("all") }}>Clear filters</button> : null}</div>
      {activeTab === "voices" && !report.checks.includes("voice") ? <p className="mt-3 text-sm">Character voice comparison was not included in this run.</p> : activeTab === "repetition" && !report.checks.includes("repetition") ? <p className="mt-3 text-sm">Overused language was not included in this run.</p> : null}

      {activeTab === "reader" ? (
        <div className="mt-6">
          <section className="border-b border-[rgb(var(--border))] pb-5">
            <h3 className="font-semibold">Overall impression</h3>
            <p className="mt-2 leading-7">{report.overall_impression}</p>
          </section>
          {(report.reader_vibe || report.story_understanding) ? (
            <div className="grid border-b border-[rgb(var(--border))] lg:grid-cols-2 lg:divide-x lg:divide-[rgb(var(--border))]">
              {report.reader_vibe ? <section className="py-5 lg:pr-5"><h3 className="font-semibold">Reader perspective</h3><p className="app-copy mt-2">{report.reader_vibe}</p></section> : null}
              {report.story_understanding ? <section className="border-t border-[rgb(var(--border))] py-5 lg:border-t-0 lg:pl-5"><h3 className="font-semibold">Story understanding</h3><p className="app-copy mt-2">{report.story_understanding}</p></section> : null}
            </div>
          ) : null}
          <div className="grid border-b border-[rgb(var(--border))] lg:grid-cols-2 lg:divide-x lg:divide-[rgb(var(--border))]">
            <section className="py-5 lg:pr-5"><h3 className="font-semibold">Strengths</h3>{report.strengths.length ? <ul className="mt-2 list-disc space-y-2 pl-5 text-sm">{report.strengths.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="app-copy mt-2">No strengths were returned for this run.</p>}</section>
            <section className="border-t border-[rgb(var(--border))] py-5 lg:border-t-0 lg:pl-5"><h3 className="font-semibold">Reader questions</h3>{report.reader_questions.length ? <ul className="mt-2 list-disc space-y-2 pl-5 text-sm">{report.reader_questions.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="app-copy mt-2">No reader questions were returned.</p>}</section>
          </div>
          <section className="border-b border-[rgb(var(--border))] py-5"><h3 className="font-semibold">Prioritized revisions</h3>{report.prioritized_revisions.length ? <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">{report.prioritized_revisions.map((item) => <li key={item}>{item}</li>)}</ol> : <p className="app-copy mt-2">No prioritized revisions were returned.</p>}</section>
          <div className="pt-5">{!filteredFindings.length ? <p className="app-copy">{report.findings.length ? "No findings match these filters." : "No individual reader findings were returned for this run."}</p> : null}{filteredFindings.map((finding) => <FindingCard key={finding.id} bookId={bookId} finding={finding} saving={savingNote} onSave={() => onSaveFinding(finding)} />)}</div>
        </div>
      ) : null}

      {activeTab === "repetition" ? (
        <div className="mt-5 divide-y divide-[rgb(var(--border))]">
          {filteredTerms.length ? filteredTerms.map((term) => (
            <article key={term.id} className="py-5 first:pt-0">
              <div className="flex flex-wrap justify-between gap-3">
                <div><h3 className="text-lg font-semibold">“{term.term}”</h3><p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">{term.kind} · {term.rate_per_1000} per 1,000 words{term.burst_detected ? " · local burst" : ""}</p></div>
                <p className="text-sm"><strong className="mr-1 text-lg">{term.count}</strong>uses · {term.narration_count} narration / {term.dialogue_count} dialogue</p>
              </div>
              <EvidenceLinks bookId={bookId} findingId={term.id} evidence={term.evidence} />
            </article>
          )) : <p className="app-copy">No repeated terms match these filters.</p>}
        </div>
      ) : null}

      {activeTab === "voices" ? (
        <div className="mt-5 divide-y divide-[rgb(var(--border))]">
          {filteredVoices.length ? filteredVoices.map((voice) => (
            <article key={voice.id} className="grid gap-3 py-5 first:pt-0 md:grid-cols-[minmax(10rem,0.65fr)_minmax(0,1fr)]">
              <div><h3 className="text-lg font-semibold">{voice.character_name}</h3><p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">{voice.confidence} confidence · {voice.sample_dialogue_count} dialogue samples · {voice.sample_word_count} words</p></div>
              {voice.distinctness_score === null ? <p className="app-copy">Not enough attributed dialogue for a reliable comparison.</p> : <div><p><strong className="text-lg">{voice.distinctness_score}%</strong> distinct</p><p className="app-copy mt-1">Closest to {voice.closest_character_name} ({voice.similarity_score}% similarity).</p><p className="mt-2 text-sm">Shared signals: {voice.shared_signals.join(", ") || "None"}</p>{voice.shared_phrases.length ? <p className="mt-1 text-sm">Shared phrases: {voice.shared_phrases.join(", ")}</p> : null}</div>}
            </article>
          )) : <p className="app-copy">No voice comparisons match this filter.</p>}
        </div>
      ) : null}

      {activeTab === "revisions" ? (
        <div className="mt-5 divide-y divide-[rgb(var(--border))]">
          {filteredCandidates.length ? filteredCandidates.map((candidate) => (
            <article key={candidate.id} className="py-5 first:pt-0">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="text-sm font-medium text-[rgb(var(--muted-foreground))]">{candidate.severity} · {candidate.category.replaceAll("_", " ")}</p><h3 className="mt-1 text-lg font-semibold">{candidate.title}</h3></div>
                <div className="flex flex-wrap gap-4"><button type="button" disabled={savingNote} onClick={() => onSaveFinding(candidate)} className="text-sm font-semibold text-[rgb(var(--accent))] hover:underline">Save note</button>{canCreateTask ? <button type="button" disabled={creatingTaskId !== null} onClick={() => onCreateTask(candidate)} className="text-sm font-semibold text-[rgb(var(--accent))] hover:underline">{creatingTaskId === candidate.id ? "Creating..." : "Create revision task"}</button> : null}</div>
              </div>
              <p className="app-copy mt-3">{candidate.description}</p><p className="mt-3 text-sm"><strong>Revision direction:</strong> {candidate.recommendation}</p>
              <EvidenceLinks bookId={bookId} findingId={candidate.id} evidence={candidate.evidence} />
            </article>
          )) : <p className="app-copy">No revision candidates match these filters.</p>}
        </div>
      ) : null}
      </div>
    </div>
  )
}
