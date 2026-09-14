"use client"

import Link from "next/link"
import type { Route } from "next"
import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef } from "react"

import { VisibilityBadge } from "@/components/ui/VisibilityBadge"
import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { renderRichTextHtml } from "@/lib/utils/richText"
import type { PublicChapter } from "@/types/book"

export function PublicChapterPageClient({
  bookId,
  chapterId,
  initialChapter = null,
}: {
  bookId: string
  chapterId: string
  initialChapter?: PublicChapter | null
}) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const chapterNum = Number.parseInt(chapterId, 10)
  const hasValidChapterNumber = Number.isFinite(chapterNum) && chapterNum > 0
  const trackedChapterKeyRef = useRef<string | null>(null)
  const {
    data: chapter = initialChapter,
    isLoading,
    isError,
  } = useQuery<PublicChapter | null>({
    queryKey: asQueryKey(`public:chapter:${bookId}:${chapterNum}`),
    queryFn: () => publicApi.getChapter(bookId, chapterNum),
    enabled: hasValidChapterNumber,
    initialData: initialChapter ?? undefined,
  })
  const { data: text = "" } = useQuery<string>({
    queryKey: asQueryKey(`public:chapter-text:${bookId}:${chapterNum}`),
    queryFn: async () => {
      const contentUrl = chapter?.content_url || chapter?.text_url
      if (!contentUrl || chapter.text_content) return chapter?.text_content || ""
      const response = await fetch(contentUrl)
      return response.text()
    },
    enabled: Boolean(chapter && (chapter.text_content || chapter.content_url || chapter.text_url)),
    initialData: initialChapter?.text_content || undefined,
  })

  useEffect(() => {
    if (!chapter || !hasValidChapterNumber) return
    const nextKey = `${chapter.book_id}:${chapter.chapter_number}`
    if (trackedChapterKeyRef.current === nextKey) return
    trackedChapterKeyRef.current = nextKey
    void publicApi.trackView(bookId, {
      eventType: "chapter_view",
      chapterNumber: chapter.chapter_number,
    })
  }, [bookId, chapter, hasValidChapterNumber])

  if (isLoading) {
    return <div className={`mx-auto max-w-4xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>Loading chapter...</div>
  }

  if (!hasValidChapterNumber || isError || !chapter) {
    return (
      <div className={`min-h-screen ${isDark ? "bg-[#0a0f14] text-white" : "bg-[#f8f7f3] text-slate-950"}`}>
        <div className="mx-auto max-w-4xl px-4 py-16 text-center">
          <VisibilityBadge state="public_sample" />
          <h1 className="mt-4 font-serif text-3xl">This chapter is not available.</h1>
          <p className={`mx-auto mt-4 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
            The author may have unpublished this sample, the chapter may have moved, or public access may no longer be enabled for this manuscript.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href={`/public/${bookId}` as Route} className={`rounded-md border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 hover:bg-white/10" : "border-slate-200 bg-slate-50 hover:bg-slate-100"}`}>
              Back to public sample
            </Link>
            <Link href="/public" className={`rounded-md border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 hover:bg-white/10" : "border-slate-200 bg-slate-50 hover:bg-slate-100"}`}>
              Showcase library
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#0a0f14] text-white" : "bg-[#f8f7f3] text-slate-950"}`}>
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Link href={`/public/${bookId}` as Route} className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>
            {"<- Back to public sample"}
          </Link>
          <Link href="/public" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>
            Showcase library
          </Link>
        </div>
        <h1 className="font-serif text-4xl">{chapter.chapter_title || `Chapter ${chapter.chapter_number}`}</h1>
        {chapter.chapter_description ? <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{chapter.chapter_description}</p> : null}
        <div
          className="note-rich-content mt-8 text-lg leading-9"
          dangerouslySetInnerHTML={{ __html: renderRichTextHtml((chapter.html_content ?? text) || "Chapter text is still syncing.") }}
        />
        <div className={`mt-10 flex flex-wrap gap-2 border-t pt-6 ${isDark ? "border-white/10" : "border-slate-200"}`}>
          {chapter.chapter_number > 1 ? (
            <Link href={`/public/${bookId}/chapter/${chapter.chapter_number - 1}` as Route} className={`rounded-md border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 hover:bg-white/10" : "border-slate-200 bg-slate-50 hover:bg-slate-100"}`}>
              Previous chapter
            </Link>
          ) : null}
          {chapter.total_chapters === null || chapter.chapter_number < chapter.total_chapters ? (
            <Link href={`/public/${bookId}/chapter/${chapter.chapter_number + 1}` as Route} className={`rounded-md border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 hover:bg-white/10" : "border-slate-200 bg-slate-50 hover:bg-slate-100"}`}>
              Next chapter
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  )
}
