"use client"

import Link from "next/link"
import { seriesSimilarityLabel, type SeriesReference } from "./seriesWikiPage.helpers"

export function SeriesReferenceDetail({ match }: { match: SeriesReference }) {
  return <div className="py-5 lg:p-6">
    <p className="text-sm text-[rgb(var(--muted-foreground))]">{match.source === "wiki" ? "Wiki reference" : "Character reference"}{match.entryType ? ` · ${match.entryType}` : ""}</p>
    <h2 className="mt-2 break-words text-xl font-semibold leading-8">{match.firstName} ↔ {match.secondName}</h2>
    <dl className="mt-5 divide-y border-y text-sm leading-6"><div className="py-4"><dt className="text-[rgb(var(--muted-foreground))]">{match.involvesCurrentBook ? "Current book reference" : "Source reference"}</dt><dd className="mt-1 font-semibold">{match.firstName}</dd><dd>{match.firstBookTitle}</dd></div><div className="py-4"><dt className="text-[rgb(var(--muted-foreground))]">Connected reference</dt><dd className="mt-1 font-semibold">{match.secondName}</dd><dd>{match.secondBookTitle}</dd></div><div className="flex flex-wrap justify-between gap-3 py-4"><dt className="text-[rgb(var(--muted-foreground))]">Similarity</dt><dd className="font-semibold">{seriesSimilarityLabel(match.similarity)}</dd></div></dl>
    <p className="mt-4 text-sm leading-6 text-[rgb(var(--muted-foreground))]">Similarity measures how closely the stored descriptions relate. It does not confirm identity, continuity, or shared canon.</p>
    <p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">This comparison contains names and scores, without chapter citations. Inspect the source context in both books before deciding whether they refer to the same character or lore.</p>
    <div className="mt-4 flex flex-wrap gap-3"><Link href={`/${encodeURIComponent(match.firstBookId)}`} className="app-button-secondary">Open source book</Link><Link href={`/${encodeURIComponent(match.secondBookId)}`} className="app-button-secondary">Open connected book</Link></div>
  </div>
}

export function SeriesReferenceList({ references, selected, onSelect, onToggle }: { references: SeriesReference[]; selected: SeriesReference | null; onSelect: (key: string) => void; onToggle: (key: string) => void }) {
  return <>
    <div className="mt-5 hidden border-y lg:grid lg:grid-cols-[minmax(20rem,.9fr)_minmax(0,1.1fr)]">
      <ul aria-label="Series references" className="max-h-[70vh] divide-y overflow-y-auto">{references.map(match => <li key={match.key}><button type="button" aria-pressed={selected?.key === match.key} className="series-reference-button w-full p-4 text-left" onClick={() => onSelect(match.key)}><span className="flex items-start justify-between gap-4"><span className="min-w-0"><span className="block text-base font-semibold">{match.firstName}</span><span className="mt-1 block text-sm leading-6 text-[rgb(var(--muted-foreground))]">{match.firstBookTitle}</span><span className="mt-2 block text-sm leading-6">Connected to {match.secondName} · {match.secondBookTitle}</span><span className="mt-2 block text-sm text-[rgb(var(--muted-foreground))]">{match.source === "wiki" ? "Wiki" : "Character"}{match.entryType ? ` · ${match.entryType}` : ""}</span></span><span className="shrink-0 text-sm font-semibold">{seriesSimilarityLabel(match.similarity)}</span></span></button></li>)}</ul>
      <aside aria-label="Selected series reference" className="min-w-0 border-l">{selected ? <SeriesReferenceDetail match={selected} /> : <p className="p-6 text-sm leading-6">Choose a reference to inspect both books. A previously selected reference may no longer be in the refreshed results.</p>}</aside>
    </div>
    <div className="mt-5 divide-y border-y lg:hidden">{references.map((match, index) => { const open = selected?.key === match.key; return <div key={match.key}><button type="button" className="series-reference-button w-full px-3 py-4 text-left" aria-expanded={open} aria-controls={open ? `series-reference-mobile-${index}` : undefined} onClick={() => onToggle(match.key)}><span className="flex items-start justify-between gap-3"><span className="min-w-0"><span className="block text-base font-semibold">{match.firstName}</span><span className="mt-1 block text-sm leading-6 text-[rgb(var(--muted-foreground))]">{match.firstBookTitle}</span><span className="mt-2 block text-sm leading-6">{match.secondName} · {match.secondBookTitle}</span><span className="mt-2 block text-sm text-[rgb(var(--muted-foreground))]">{open ? "Hide reference" : "View reference"}</span></span><span className="shrink-0 text-sm font-semibold">{seriesSimilarityLabel(match.similarity)}</span></span></button>{open ? <div id={`series-reference-mobile-${index}`}><SeriesReferenceDetail match={match} /></div> : null}</div> })}</div>
  </>
}
