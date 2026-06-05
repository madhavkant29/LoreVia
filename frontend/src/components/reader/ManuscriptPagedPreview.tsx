"use client"

import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react"
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
  const dragStateRef = useRef<{ pointerId: number; startPage: number; startX: number; startScrollLeft: number; moved: boolean } | null>(null)
  const shellRef = useRef<HTMLDivElement | null>(null)
  const previewRef = useRef<HTMLDivElement | null>(null)
  const [pageCount, setPageCount] = useState(1)
  const [currentPage, setCurrentPage] = useState(1)
  const [isDragging, setIsDragging] = useState(false)

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
    const countPages = () => {
      const scrollWidth = shell.scrollWidth
      const clientWidth = shell.clientWidth
      return scrollWidth <= clientWidth + 1
        ? 1
        : Math.max(2, Math.ceil((scrollWidth + layout.pageGapPx) / pageExtent))
    }

    const syncPageMetrics = () => {
      const totalPages = countPages()

      setPageCount((current) => current === totalPages ? current : totalPages)
      setCurrentPage((current) => Math.min(totalPages, Math.max(1, current)))
      onPageCountChange?.(totalPages)
    }

    const syncCurrentPage = () => {
      const totalPages = countPages()
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
  }, [layout, onPageCountChange, sectionMarkup.length])

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
  const goToPage = (page: number) => {
    const shell = shellRef.current
    if (!shell) return
    const nextPage = Math.min(pageCount, Math.max(1, page))
    const pageExtent = getManuscriptPreviewPageExtentPx(layout)
    shell.scrollTo({ left: (nextPage - 1) * pageExtent, behavior: "smooth" })
    setCurrentPage(nextPage)
  }

  const finishDrag = (pointerId?: number) => {
    const shell = shellRef.current
    const dragState = dragStateRef.current
    if (!shell || !dragState) return
    if (pointerId !== undefined && dragState.pointerId !== pointerId) return

    dragStateRef.current = null
    setIsDragging(false)
    if (!("hasPointerCapture" in shell) || !shell.hasPointerCapture(dragState.pointerId)) {
      // no-op when the browser already dropped capture
    } else {
      shell.releasePointerCapture(dragState.pointerId)
    }

    if (!dragState.moved) return

    const pageExtent = getManuscriptPreviewPageExtentPx(layout)
    const dragDistance = shell.scrollLeft - dragState.startScrollLeft
    const threshold = Math.min(120, pageExtent * 0.18)
    const pageDelta = Math.abs(dragDistance) < threshold
      ? 0
      : Math.max(1, Math.round(Math.abs(dragDistance) / pageExtent)) * Math.sign(dragDistance)
    const nearestPage = Math.min(pageCount, Math.max(1, dragState.startPage + pageDelta))
    shell.scrollTo({ left: (nearestPage - 1) * pageExtent, behavior: "smooth" })
    setCurrentPage(nearestPage)
  }

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    const shell = shellRef.current
    if (!shell || pageCount <= 1 || event.button !== 0) return
    if (event.target instanceof HTMLElement && event.target.closest("a, button, input, select, textarea, summary")) return

    dragStateRef.current = {
      pointerId: event.pointerId,
      startPage: currentPage,
      startX: event.clientX,
      startScrollLeft: shell.scrollLeft,
      moved: false,
    }
    setIsDragging(false)
    shell.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const shell = shellRef.current
    const dragState = dragStateRef.current
    if (!shell || !dragState || dragState.pointerId !== event.pointerId) return

    const deltaX = event.clientX - dragState.startX
    if (!dragState.moved && Math.abs(deltaX) > 4) {
      dragState.moved = true
      setIsDragging(true)
    }
    if (!dragState.moved) return

    event.preventDefault()
    shell.scrollLeft = dragState.startScrollLeft - deltaX
  }

  return (
    <div
      className={`rounded-lg border p-4 ${
        isDark ? "border-white/10 bg-[#0c1118]/92" : "border-[#d8d0c4] bg-[#f8f4ee]"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>
            Read-only paged preview
          </p>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            {layout.label}
          </p>
        </div>
        <div className={`flex flex-wrap items-center gap-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          <select
            aria-label="Preview fit"
            defaultValue="fit-page"
            className={`rounded-md border px-3 py-2 text-xs font-medium ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
          >
            <option value="fit-page">Fit to page</option>
          </select>
          <button
            type="button"
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
            aria-label="Previous preview page"
            className={`rounded-md border px-3 py-2 font-semibold disabled:opacity-40 ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage >= pageCount}
            aria-label="Next preview page"
            className={`rounded-md border px-3 py-2 font-semibold disabled:opacity-40 ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
          >
            Next
          </button>
          <span className={`rounded-full px-3 py-1.5 ${isDark ? "bg-white/8 text-slate-200" : "bg-white text-stone-700"}`}>
            Page {currentPage} of {pageCount}
          </span>
        </div>
      </div>

      <div
        ref={shellRef}
        data-testid="manuscript-paged-preview-shell"
        data-preview-page-count={pageCount}
        className={`manuscript-paged-preview-shell relative mx-auto mt-4 rounded-md border ${
          pageCount > 1 ? (isDragging ? "cursor-grabbing select-none" : "cursor-grab") : ""
        } ${
          isDark ? "border-white/10 bg-[#05070a]" : "border-[#e7dfd3] bg-[#efe6d8]"
        }`}
        style={previewStyle}
        onPointerCancel={(event) => finishDrag(event.pointerId)}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={(event) => finishDrag(event.pointerId)}
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
        <div className="pointer-events-none absolute bottom-6 left-1/2 -translate-x-1/2 font-serif text-xs text-stone-500">
          {currentPage}
        </div>
      </div>
    </div>
  )
}
