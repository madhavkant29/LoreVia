import Link from "next/link"
import type { TimelineChapter } from "@/types/reader"
import { timelineRangeLabel, visibleTimelineSpan, type TimelineItem } from "./timelinePage.helpers"

const CELL_WIDTH = 80
export const timelineButton = "app-button-secondary !rounded-sm disabled:cursor-not-allowed disabled:opacity-50"
export const timelineMuted = "text-[rgb(var(--muted-foreground))]"

export function TimelineSource({ bookId, chapters, start, end }: { bookId: string; chapters: TimelineChapter[]; start: number; end: number }) {
  const span = visibleTimelineSpan(chapters, start, end)
  return <div className="mt-2 text-sm leading-6">
    <p>{timelineRangeLabel(start, end)}</p>
    {span ? <div className="flex flex-wrap gap-x-4">
      <Link className="underline underline-offset-4 hover:opacity-80" href={`/${bookId}/chapter/${chapters[span.start].number}`}>Open chapter {chapters[span.start].number}</Link>
      {span.end !== span.start ? <Link className="underline underline-offset-4 hover:opacity-80" href={`/${bookId}/chapter/${chapters[span.end].number}`}>Open chapter {chapters[span.end].number}</Link> : null}
    </div> : <p className={timelineMuted}>No available chapter for this entry.</p>}
  </div>
}

export function TimelineList({ items, chapters, bookId }: { items: TimelineItem[]; chapters: TimelineChapter[]; bookId: string }) {
  return <section aria-label="Timeline list" className="mt-5">
    <h2 className="text-lg font-semibold">Timeline list</h2>
    <p className={`mt-1 text-sm ${timelineMuted}`}>Character spans, plot threads, and relationship turns, ordered by chapter.</p>
    <ol className="mt-3 divide-y divide-[rgb(var(--border)/0.7)] border-y border-[rgb(var(--border)/0.7)]">
      {items.map((item) => <li key={item.id} className="py-4">
        <p className={`text-sm capitalize ${timelineMuted}`}>{item.kind.replaceAll("_", " ")}</p>
        <h3 className="mt-1 text-base font-semibold">{item.title}</h3>
        {item.detail ? <p className={`mt-1 max-w-3xl text-sm leading-6 ${timelineMuted}`}>{item.detail}</p> : null}
        <TimelineSource bookId={bookId} chapters={chapters} start={item.start} end={item.end} />
      </li>)}
      {!items.length ? <li className={`py-6 text-sm ${timelineMuted}`}>No items match this lane. Choose another category in Show.</li> : null}
    </ol>
  </section>
}

const sections = [
  { id: "characters", title: "Characters", subtitle: "Recorded chapter spans for each character" },
  { id: "plotThreads", title: "Plot threads", subtitle: "Open and resolved arcs over time" },
  { id: "relationships", title: "Relationship shifts", subtitle: "Turning points between characters" },
] as const

export function TimelineLanes({ items, chapters, bookId, isDark, activeLane, collapsed, onToggle }: {
  items: TimelineItem[]; chapters: TimelineChapter[]; bookId: string; isDark: boolean; activeLane: string
  collapsed: Record<string, boolean>; onToggle: (section: "characters" | "plotThreads" | "relationships", value: boolean) => void
}) {
  const border = isDark ? "border-white/15" : "border-stone-300"
  const background = isDark ? "bg-[#111718]" : "bg-white"
  return <section className="mt-5" aria-label="Timeline lanes">
    <p className={`mb-3 text-sm leading-6 ${timelineMuted}`}>Bars show recorded chapter spans; markers show relationship turns. Scroll horizontally for more chapters, or choose List view.</p>
    <div role="region" aria-label="Chapter lanes, horizontally scrollable" tabIndex={0} className={`max-w-full overflow-x-auto rounded-sm border ${border} ${background}`}>
      <div className="min-w-max">
        <div className={`flex border-b ${border}`}>
          <h2 className={`sticky left-0 z-10 w-64 shrink-0 border-r px-4 py-4 text-sm font-semibold md:w-80 ${border} ${background}`}>Timeline lanes</h2>
          {chapters.map((chapter) => <Link key={chapter.number} href={`/${bookId}/chapter/${chapter.number}`} aria-label={`Chapter ${chapter.number}${chapter.title ? `: ${chapter.title}` : ""}`} className={`shrink-0 border-r px-2 py-4 text-center text-sm underline underline-offset-4 ${border}`} style={{ width: CELL_WIDTH }}>Ch. {chapter.number}</Link>)}
        </div>
        {sections.filter((section) => activeLane === "all" || activeLane === section.id).map((section) => {
          const rows = items.filter((item) => item.lane === section.id)
          return <section key={section.id} className={`border-b last:border-b-0 ${border}`}>
            <h3 className={`sticky left-0 w-64 md:w-80 ${background}`}>
              <button type="button" aria-expanded={!collapsed[section.id]} aria-controls={`timeline-${section.id}-rows`} onClick={() => onToggle(section.id, !collapsed[section.id])} className="w-full px-4 py-4 text-left hover:bg-[rgb(var(--foreground)/0.04)]">
                <span className="text-sm font-semibold"><span aria-hidden="true">{collapsed[section.id] ? "+" : "−"} </span>{section.title} ({rows.length})</span>
                <span className={`mt-1 block text-sm font-normal ${timelineMuted}`}>{section.subtitle}</span>
              </button>
            </h3>
            <div id={`timeline-${section.id}-rows`} hidden={!!collapsed[section.id]}>
              {!rows.length ? <p className={`sticky left-0 w-64 px-4 pb-5 text-sm md:w-80 ${timelineMuted}`}>No {section.title.toLowerCase()} recorded in available chapters.</p> : null}
              {rows.map((item) => {
                const span = visibleTimelineSpan(chapters, item.start, item.end)
                return <div key={item.id} className={`flex border-t ${border}`}>
                  <div className={`sticky left-0 z-[1] w-64 shrink-0 border-r px-4 py-4 md:w-80 ${border} ${background}`}>
                    <h4 className="text-base font-semibold">{item.title}</h4>
                    <p className={`mt-1 text-sm capitalize ${timelineMuted}`}>{item.kind.replaceAll("_", " ")}</p>
                    {item.detail ? <p className={`mt-2 text-sm leading-6 ${timelineMuted}`}>{item.detail}</p> : null}
                    <TimelineSource bookId={bookId} chapters={chapters} start={item.start} end={item.end} />
                  </div>
                  <div aria-hidden="true" className="relative flex">
                    {chapters.map((chapter, index) => <div key={chapter.number} style={{ width: CELL_WIDTH }} className={`shrink-0 border-r ${border} ${index % 2 === 0 ? "bg-[rgb(var(--foreground)/0.025)]" : ""}`} />)}
                    {span ? <div data-timeline-mark={item.id} className={`absolute top-1/2 h-3 -translate-y-1/2 ${item.lane === "relationships" ? "bg-amber-500" : item.lane === "characters" ? "bg-emerald-500" : item.kind === "resolved" ? "bg-stone-400" : "bg-violet-500"}`} style={{ left: span.start * CELL_WIDTH + (item.lane === "relationships" ? 34 : 6), width: item.lane === "relationships" ? 12 : (span.end - span.start + 1) * CELL_WIDTH - 12 }} /> : null}
                  </div>
                </div>
              })}
            </div>
          </section>
        })}
      </div>
    </div>
  </section>
}

