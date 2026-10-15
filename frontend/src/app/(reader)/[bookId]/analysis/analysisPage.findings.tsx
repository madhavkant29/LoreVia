import { useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import type { ContinuityFinding } from "@/types/book"
import { filterFindings, findingChapter, partitionFindings, type FindingGroup } from "./analysisPage.helpers"

const labels: Record<FindingGroup, string> = { pending: "Needs review", reviewed: "Reviewed", stale: "Stale after edits" }

export function FindingsList({ bookId, findings, isDark }: { bookId: string; findings: ContinuityFinding[]; isDark: boolean }) {
  const [group, setGroup] = useState<FindingGroup>("pending")
  const [query, setQuery] = useState("")
  const [limit, setLimit] = useState(12)
  const groups = partitionFindings(findings)
  const visible = filterFindings(groups[group], query)
  const secondary = isDark ? "text-slate-400" : "text-stone-600"
  const border = isDark ? "border-white/10" : "border-stone-200"

  return <>
    <div className={`mt-6 flex flex-wrap gap-x-5 border-y ${border}`} role="group" aria-label="Finding status">
      {(Object.keys(labels) as FindingGroup[]).map((value) => <button
        key={value} type="button" aria-pressed={group === value}
        onClick={() => { setGroup(value); setLimit(12) }}
        className={`min-h-12 border-b-2 py-3 text-sm ${group === value ? isDark ? "border-teal-300 text-white" : "border-teal-700 text-stone-950" : `border-transparent ${secondary}`}`}
      >{labels[value]} <span className="ml-2 font-semibold tabular-nums">{groups[value].length}</span></button>)}
    </div>
    <section className="mt-6" aria-label="Continuity findings">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <h2 className="text-xl font-semibold">Continuity findings</h2>
          <p className={`mt-1 text-sm leading-6 ${secondary}`}>Check possible conflicts against the cited manuscript evidence before deciding what to revise.</p>
        </div>
        <Link href={`/${bookId}/author-loop#revision-control` as Route} prefetch={false} className={`text-sm font-medium underline underline-offset-4 ${isDark ? "text-teal-300" : "text-teal-800"}`}>Resume revision workflow</Link>
      </div>
      <div className="mt-5 flex flex-wrap items-end gap-3">
        <label className={`w-full max-w-md text-sm ${secondary}`}>Search findings
          <input value={query} onChange={(event) => { setQuery(event.target.value); setLimit(12) }} placeholder="Title, character, category, or severity" className={`mt-2 block w-full rounded-sm border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-[#0b1514] text-slate-100" : "border-stone-300 bg-white text-stone-900"}`} />
        </label>
        {query ? <button type="button" onClick={() => setQuery("")} className="min-h-11 px-2 text-sm underline">Clear search</button> : null}
        <p role="status" className={`py-3 text-sm ${secondary}`}>{visible.length} {visible.length === 1 ? "finding" : "findings"} · {labels[group]}</p>
      </div>
      {group === "stale" ? <p className={`mt-3 text-sm leading-6 ${secondary}`}>These findings refer to an earlier manuscript version. Recheck them against your latest draft before acting.</p> : null}
      {visible.length ? <div className={`mt-3 divide-y border-y ${isDark ? "divide-white/10" : "divide-stone-200"} ${border}`}>
        {visible.slice(0, limit).map((finding) => {
          const chapter = findingChapter(finding)
          return <article key={finding.id} className="grid gap-3 py-5 lg:grid-cols-[8rem_minmax(0,1fr)] lg:gap-5">
            <div className={`text-sm leading-6 ${secondary}`}>
              <p className="font-medium capitalize">{finding.severity}</p>
              <p className="break-words capitalize">{finding.category.replaceAll("_", " ")}</p>
              {finding.decision ? <p className="mt-2 capitalize">Decision: {finding.decision.replaceAll("_", " ")}</p> : null}
            </div>
            <div className="min-w-0">
              <h3 className="break-words text-base font-semibold">{finding.title}</h3>
              <p className={`mt-2 max-w-3xl break-words text-sm leading-7 ${secondary}`}>{finding.explanation}</p>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
                {chapter ? <Link href={`/${bookId}/chapter/${chapter}` as Route} className="underline underline-offset-4">Chapter {chapter}</Link> : null}
                <Link href={`/${bookId}/advisor` as Route} prefetch={false} className="underline underline-offset-4">Investigate in Story Advisor</Link>
              </div>
              <details className={`mt-4 border-l-2 pl-4 ${border}`}>
                <summary className="cursor-pointer py-1 text-sm font-medium">Evidence and recommendation</summary>
                {finding.recommendation ? <p className={`mt-3 break-words text-sm leading-6 ${secondary}`}>{finding.recommendation}</p> : null}
                {finding.evidence.length ? <ol className="mt-3 space-y-4">
                  {finding.evidence.map((evidence, index) => <li key={`${evidence.observation_id}-${index}`}>
                    <p className={`text-sm ${secondary}`}>{evidence.subject_label}{Number.isInteger(evidence.chapter_number) && evidence.chapter_number > 0 ? ` · Chapter ${evidence.chapter_number}` : " · Chapter unavailable"}</p>
                    <blockquote className="mt-1 break-words text-sm leading-7">{evidence.excerpt || evidence.display_value || "No excerpt available."}</blockquote>
                    {Number.isInteger(evidence.chapter_number) && evidence.chapter_number > 0 ? <Link href={`/${bookId}/chapter/${evidence.chapter_number}` as Route} className="mt-1 inline-block py-1 text-sm underline">Read source chapter {evidence.chapter_number}</Link> : null}
                  </li>)}
                </ol> : <p className={`mt-3 text-sm ${secondary}`}>No manuscript excerpts are attached to this finding. Verify the claim in your draft.</p>}
                {finding.reason ? <p className={`mt-3 break-words text-sm ${secondary}`}>Review note: {finding.reason.replaceAll("_", " ")}</p> : null}
              </details>
            </div>
          </article>
        })}
      </div> : <div className={`mt-4 border-y py-6 text-sm leading-6 ${border} ${secondary}`}>
        {query ? "No findings match this search. Clear it or choose another status." : group === "pending" ? "No current continuity finding needs a decision. Focused reviews remain available below." : group === "reviewed" ? "No reviewed findings yet. Use the revision workflow to record a decision." : "No findings are marked stale after edits."}
      </div>}
      {visible.length > limit ? <button type="button" onClick={() => setLimit((value) => value + 12)} className={`mt-4 min-h-11 rounded-sm border px-4 text-sm ${border}`}>Show more findings ({visible.length - limit} remaining)</button> : null}
    </section>
  </>
}
