"use client"

import { useEffect, useRef, useState } from "react"

import { capture } from "@/lib/analytics/posthog"

import type { TableOfContentsItem } from "@/content/types"

function CopyIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <rect x="8" y="8" width="11" height="11" rx="2" />
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </svg>
  )
}

function ShareIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <circle cx="18" cy="5" r="2.5" />
      <circle cx="6" cy="12" r="2.5" />
      <circle cx="18" cy="19" r="2.5" />
      <path d="m8.2 10.8 7.6-4.5M8.2 13.2l7.6 4.5" />
    </svg>
  )
}

function fallbackCopy(value: string): boolean {
  const textarea = document.createElement("textarea")
  textarea.value = value
  textarea.setAttribute("readonly", "")
  textarea.style.position = "fixed"
  textarea.style.opacity = "0"
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand("copy")
  textarea.remove()
  return copied
}

export function ReaderTools({
  kind,
  slug,
  title,
  tableOfContents,
}: {
  kind: "blog" | "answer"
  slug: string
  title: string
  tableOfContents: TableOfContentsItem[]
}) {
  const [progress, setProgress] = useState(0)
  const [feedback, setFeedback] = useState("")
  const reachedDepth = useRef(new Set<number>())

  useEffect(() => {
    const article = document.querySelector<HTMLElement>("[data-editorial-body]")
    if (!article) return

    const updateProgress = () => {
      const rect = article.getBoundingClientRect()
      const scrollable = Math.max(1, article.offsetHeight - window.innerHeight * 0.55)
      const nextProgress = Math.max(0, Math.min(100, ((window.innerHeight * 0.22 - rect.top) / scrollable) * 100))
      setProgress(nextProgress)

      for (const milestone of [25, 50, 75, 100]) {
        if (nextProgress >= milestone && !reachedDepth.current.has(milestone)) {
          reachedDepth.current.add(milestone)
          capture("editorial_article_depth", { kind, slug, depth_percent: milestone })
        }
      }
    }

    updateProgress()
    window.addEventListener("scroll", updateProgress, { passive: true })
    window.addEventListener("resize", updateProgress)
    return () => {
      window.removeEventListener("scroll", updateProgress)
      window.removeEventListener("resize", updateProgress)
    }
  }, [kind, slug])

  useEffect(() => {
    const onTrackedClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-editorial-event]") : null
      if (!target) return
      capture(target.dataset.editorialEvent ?? "editorial_link_opened", {
        kind,
        slug,
        destination: target.dataset.editorialDestination,
      })
    }
    document.addEventListener("click", onTrackedClick)
    return () => document.removeEventListener("click", onTrackedClick)
  }, [kind, slug])

  const copyCurrentUrl = async () => {
    const url = window.location.href
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(url)
      else if (!fallbackCopy(url)) throw new Error("Copy unavailable")
      setFeedback("Link copied")
      capture("editorial_article_shared", { kind, slug, method: "copy" })
    } catch {
      setFeedback("Copy failed. Select the address from your browser.")
    }
  }

  const share = async () => {
    try {
      if (!navigator.share) {
        await copyCurrentUrl()
        return
      }
      await navigator.share({ title, url: window.location.href })
      setFeedback("Share sheet opened")
      capture("editorial_article_shared", { kind, slug, method: "web_share" })
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return
      await copyCurrentUrl()
    }
  }

  return (
    <>
      <div className="editorial-progress" aria-hidden="true">
        <span style={{ transform: `scaleX(${progress / 100})` }} />
      </div>

      <div className="editorial-reader-tools">
        <button type="button" onClick={copyCurrentUrl} className="editorial-icon-button" aria-label="Copy article link">
          <CopyIcon />
          <span>Copy link</span>
        </button>
        <button type="button" onClick={share} className="editorial-icon-button" aria-label="Share article">
          <ShareIcon />
          <span>Share</span>
        </button>
        <p className="sr-only" aria-live="polite">{feedback}</p>
      </div>

      <details className="editorial-mobile-toc">
        <summary>Jump to a section</summary>
        <nav aria-label="Article sections">
          {tableOfContents.map((item) => (
            <a key={item.id} href={`#${item.id}`}>{item.label}</a>
          ))}
        </nav>
      </details>
    </>
  )
}
