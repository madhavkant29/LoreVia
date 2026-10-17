"use client"

import Link from "next/link"
import type { Route } from "next"
import { useMemo, useState } from "react"

export type AnswerExplorerItem = {
  slug: string
  title: string
  description: string
  category: string
  readTime: string
  parentSlug: string
  parentTitle: string
}

export function AnswerExplorer({ items }: { items: AnswerExplorerItem[] }) {
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("All topics")
  const categories = ["All topics", ...Array.from(new Set(items.map((item) => item.category))).sort()]
  const normalizedQuery = query.trim().toLocaleLowerCase()

  const groups = useMemo(() => {
    const filtered = items.filter((item) => {
      const matchesCategory = category === "All topics" || item.category === category
      const haystack = `${item.title} ${item.description} ${item.parentTitle}`.toLocaleLowerCase()
      return matchesCategory && (!normalizedQuery || haystack.includes(normalizedQuery))
    })
    const grouped = new Map<string, AnswerExplorerItem[]>()
    for (const item of filtered) {
      grouped.set(item.parentSlug, [...(grouped.get(item.parentSlug) ?? []), item])
    }
    return Array.from(grouped.entries())
  }, [category, items, normalizedQuery])

  return (
    <section className="editorial-answer-explorer" aria-labelledby="answer-library-title">
      <div className="editorial-search-row">
        <label>
          <span>Search answers</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search continuity, characters, revision…"
          />
        </label>
        <label>
          <span>Topic</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            {categories.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
      </div>

      <p className="editorial-results-count" aria-live="polite">
        {groups.reduce((total, [, groupItems]) => total + groupItems.length, 0)} answers
      </p>

      {groups.length ? groups.map(([parentSlug, groupItems]) => (
        <section key={parentSlug} className="editorial-answer-group">
          <div className="editorial-answer-group__heading">
            <div>
              <p className="editorial-kicker">Broader guide</p>
              <h2 id={`group-${parentSlug}`}>{groupItems[0].parentTitle}</h2>
            </div>
            <Link href={`/blog/${parentSlug}` as Route}>Read the guide</Link>
          </div>
          <div className="editorial-answer-list" aria-labelledby={`group-${parentSlug}`}>
            {groupItems.map((item) => (
              <article key={item.slug}>
                <p className="editorial-kicker">{item.category} · {item.readTime}</p>
                <h3><Link href={`/answers/${item.slug}` as Route}>{item.title}</Link></h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </section>
      )) : (
        <div className="editorial-empty-state">
          <h2>No answers found</h2>
          <p>Try a broader phrase or choose a different topic.</p>
          <button type="button" onClick={() => { setQuery(""); setCategory("All topics") }}>Clear search</button>
        </div>
      )}
    </section>
  )
}
