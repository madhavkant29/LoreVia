"use client"

import Link from "next/link"
import type { Route } from "next"
import { useEffect, useState } from "react"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { renderRichTextHtml } from "@/lib/utils/richText"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicChapter } from "@/types/book"

export default function PublicChapterPage() {
  const { bookId, chapterId } = useParams<{ bookId: string; chapterId: string }>()
  const [chapter, setChapter] = useState<PublicChapter | null>(null)
  const [text, setText] = useState("")
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const chapterNum = parseInt(chapterId)

  useEffect(() => {
    booksApi.getPublicChapter(bookId, chapterNum).then((payload) => {
      setChapter(payload)
      if (payload.text_content) {
        setText(payload.text_content)
      } else if (payload.text_url) {
        fetch(payload.text_url).then((r) => r.text()).then(setText).catch(() => setText(""))
      } else {
        setText("")
      }
    })
  }, [bookId, chapterNum])

  if (!chapter) {
    return <div className={`mx-auto max-w-4xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>Loading chapter...</div>
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-black text-white" : "bg-white text-slate-950"}`}>
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Link href={`/public/${bookId}` as Route} className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>
            {"<- Back to public book"}
          </Link>
          <Link href="/public" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>
            Public library
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
            <Link href={`/public/${bookId}/chapter/${chapter.chapter_number - 1}` as Route} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 hover:bg-white/10" : "border-slate-200 bg-slate-50 hover:bg-slate-100"}`}>
              Previous chapter
            </Link>
          ) : null}
          {chapter.total_chapters === null || chapter.chapter_number < chapter.total_chapters ? (
            <Link href={`/public/${bookId}/chapter/${chapter.chapter_number + 1}` as Route} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 hover:bg-white/10" : "border-slate-200 bg-slate-50 hover:bg-slate-100"}`}>
              Next chapter
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  )
}
