"use client"

import type { CSSProperties } from "react"
import { useEffect, useMemo, useRef, useState } from "react"

import type { PublishingPreset } from "@/types/book"
import {
  getManuscriptPreviewContentWidthMm,
  getManuscriptPreviewLayout,
  getManuscriptPreviewPageExtentPx,
} from "@/lib/utils/manuscriptPreview"
import { renderRichTextHtml } from "@/lib/utils/richText"

export interface ManuscriptPagedPreviewSection {
  id: string
  eyebrow?: string
  title: string
  html: string
}

export function ManuscriptPagedPreview({
  sections,
  preset,
  firstLineIndent,
  lineHeight,
  isDark,
  onPageCountChange,
}: {
  sections: ManuscriptPagedPreviewSection[]
  preset: PublishingPreset["active_preset"] | null | undefined
  firstLineIndent: boolean
  lineHeight: number
  isDark: boolean
  onPageCountChange?: (count: number) => void
}) {
  const shellRef = useRef<HTMLDivElement | null>(null)
  const previewRef = useRef<HTMLDivElement | null>(null)
  const [pageCount, setPageCount] = useState(1)
  const [currentPage, setCurrentPage] = useState(1)

  const layout = useMemo(() => getManuscriptPreviewLayout(preset), [preset])
  const contentWidthMm = useMemo(() => getManuscriptPreviewContentWidthMm(layout), [layout])
  const sectionMarkup = useMemo(() => sections.map((section) => ({
    ...section,
    html: renderRichTextHtml(section.html || "<p></p>"),
  })), [sections])

  useEffect(() => {
    const shell = shellRef.current
    if (!shell) return

    const pageExtent = getManuscriptPreviewPageExtentPx(layout)
    const syncPageMetrics = () => {
      const scrollWidth = shell.scrollWidth
      const clientWidth = shell.clientWidth
      const totalPages = scrollWidth <= clientWidth + 1
        ? 1
        : Math.max(2, Math.round((scrollWidth + layout.pageGapPx) / pageExtent))

      setPageCount(totalPages)
      setCurrentPage((current) => Math.min(totalPages, Math.max(1, current)))
      onPageCountChange?.(totalPages)
    }

    const syncCurrentPage = () => {
      const totalPages = Math.max(1, pageCount)
      const nextPage = Math.min(totalPages, Math.max(1, Math.round(shell.scrollLeft / pageExtent) + 1))
      setCurrentPage(nextPage)
    }

    const observer = new ResizeObserver(() => {
      syncPageMetrics()
      syncCurrentPage()
    })

    observer.observe(shell)
    if (previewRef.current) {
      observer.observe(previewRef.current)
    }

    const animation = window.requestAnimationFrame(() => {
      syncPageMetrics()
      syncCurrentPage()
    })

    shell.addEventListener("scroll", syncCurrentPage)
    return () => {
      shell.removeEventListener("scroll", syncCurrentPage)
      observer.disconnect()
      window.cancelAnimationFrame(animation)
    }
  }, [layout, onPageCountChange, pageCount, sectionMarkup.length])

  const previewStyle = {
    "--manuscript-page-width": `${layout.pageWidthMm}mm`,
    "--manuscript-page-height": `${layout.pageHeightMm}mm`,
    "--manuscript-page-gap": `${layout.pageGapPx}px`,
    "--manuscript-page-padding-top": `${layout.paddingTopMm}mm`,
    "--manuscript-page-padding-right": `${layout.paddingRightMm}mm`,
    "--manuscript-page-padding-bottom": `${layout.paddingBottomMm}mm`,
    "--manuscript-page-padding-left": `${layout.paddingLeftMm}mm`,
    "--manuscript-page-content-width": `${contentWidthMm}mm`,
    fontFamily: layout.fontFamily,
    fontSize: `${layout.fontSizePt}pt`,
    lineHeight: String(lineHeight),
  } as CSSProperties

  return (
    <div
      className={`rounded-[1.6rem] border p-4 shadow-[0_24px_80px_-55px_rgba(15,23,42,0.28)] ${
        isDark ? "border-white/10 bg-[#0d1117]" : "border-[#d8d0c4] bg-[#f8f4ee]"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>
            Read-only paged preview
          </p>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Browser pagination follows the active export preset more closely than the draft page estimate.
          </p>
        </div>
        <div className={`flex flex-wrap items-center gap-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          <span className={`rounded-full px-3 py-1.5 ${isDark ? "bg-white/8 text-slate-200" : "bg-white text-stone-700"}`}>
            {layout.label}
          </span>
          <span className={`rounded-full px-3 py-1.5 ${isDark ? "bg-white/8 text-slate-200" : "bg-white text-stone-700"}`}>
            Page {currentPage} of {pageCount}
          </span>
        </div>
      </div>

      <div
        ref={shellRef}
        data-testid="manuscript-paged-preview-shell"
        data-preview-page-count={pageCount}
        className={`manuscript-paged-preview-shell mt-4 rounded-[1.25rem] border ${
          isDark ? "border-white/10 bg-[#06090f]" : "border-[#e7dfd3] bg-[#efe6d8]"
        }`}
        style={previewStyle}
      >
        <div
          ref={previewRef}
          className="manuscript-paged-preview"
          data-first-line-indent={firstLineIndent ? "true" : "false"}
        >
          {sectionMarkup.map((section, index) => (
            <section key={section.id} className={`manuscript-paged-preview__section ${index > 0 ? "manuscript-paged-preview__section--chapter-break" : ""}`}>
              {section.eyebrow ? (
                <p className="manuscript-paged-preview__eyebrow">{section.eyebrow}</p>
              ) : null}
              <h2 className="manuscript-paged-preview__title">{section.title}</h2>
              <div
                className="manuscript-paged-preview__body note-rich-content"
                dangerouslySetInnerHTML={{ __html: section.html }}
              />
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
