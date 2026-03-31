"use client"
import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { readerApi } from "@/lib/api/reader"
import type { ChapterListResponse, ChapterSummary } from "@/types/reader"

export default function ChapterListPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [data, setData] = useState<ChapterListResponse | null>(null)
  const [theme, setTheme] = useState<"light" | "dark">("light")
  const [expandedChapter, setExpandedChapter] = useState<number | null>(null)
  const [summaryMap, setSummaryMap] = useState<Record<number, ChapterSummary>>({})
  const [summaryError, setSummaryError] = useState<string | null>(null)

  useEffect(() => {
    readerApi.getChapterList(bookId).then(setData)
    const stored = window.localStorage.getItem("reader-theme")
    if (stored === "dark" || stored === "light") setTheme(stored)
  }, [bookId])

  const toggleRead = async (chapterNumber: number, nextRead: boolean) => {
    await readerApi.updateChapterReadStatus(bookId, chapterNumber, nextRead)
    setData((current) => current ? {
      ...current,
      chapters: current.chapters.map((chapter) =>
        chapter.number === chapterNumber ? { ...chapter, read: nextRead } : chapter
      ),
    } : current)
  }

  const toggleSummary = async (chapterNumber: number, read: boolean, intelligenceAvailable?: boolean) => {
    if (!read || intelligenceAvailable === false) return
    if (expandedChapter === chapterNumber) {
      setExpandedChapter(null)
      return
    }
    setSummaryError(null)
    if (!summaryMap[chapterNumber]) {
      try {
        const summary = await readerApi.getSummary(bookId, chapterNumber, "detailed")
        setSummaryMap((current) => ({ ...current, [chapterNumber]: summary }))
      } catch (e: any) {
        setSummaryError(e.response?.data?.detail ?? "Summary unavailable")
      }
    }
    setExpandedChapter(chapterNumber)
  }

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${theme === "dark" ? "bg-black text-white" : "bg-white text-black"}`}>
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => router.back()} className={theme === "dark" ? "text-sm text-gray-400 hover:text-white" : "text-sm text-gray-400 hover:text-gray-600"}>{"<- Back"}</button>
          <h1 className="text-2xl font-semibold">Chapters</h1>
          {data && <p className={theme === "dark" ? "text-sm text-gray-400 ml-auto" : "text-sm text-gray-500 ml-auto"}>Current chapter {data.current_chapter ?? data.read_upto}</p>}
        </div>

        <div className="flex flex-col gap-3">
          {summaryError ? (
            <div className={theme === "dark" ? "rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-200" : "rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800"}>
              {summaryError}
            </div>
          ) : null}
          {(data?.chapters ?? []).map((chapter) => (
            <div
              key={chapter.number}
              className={`rounded-xl border p-4 transition-colors ${
                theme === "dark"
                  ? chapter.read
                    ? "border-white/15 bg-white/5 hover:bg-white/10"
                    : "border-white/10 bg-black hover:bg-white/[0.03]"
                  : chapter.read
                    ? "border-gray-200 bg-gray-50 hover:bg-gray-100"
                    : "border-gray-200 bg-white hover:bg-gray-50"
              }`}
            >
              <div className="flex items-start gap-3">
                <div className={`mt-0.5 h-2.5 w-2.5 rounded-full shrink-0 ${chapter.read ? "bg-emerald-500" : "bg-gray-400"}`} />
                <div className="min-w-0 flex-1">
                  <Link href={`/${bookId}/chapter/${chapter.number}`} className="block">
                    <p className="text-sm font-semibold">Chapter {chapter.number}</p>
                    <p className={theme === "dark" ? "text-sm text-gray-300 mt-1" : "text-sm text-gray-700 mt-1"}>
                      {chapter.title || "Untitled chapter"}
                    </p>
                  </Link>
                </div>
                {chapter.read ? (
                  <button
                    type="button"
                    onClick={() => toggleSummary(chapter.number, chapter.read, chapter.intelligence_available)}
                    disabled={chapter.intelligence_available === false}
                    className={theme === "dark" ? "rounded-full border border-white/15 px-2 py-1 text-[11px] text-gray-300 hover:bg-white/5 disabled:opacity-40 disabled:hover:bg-transparent" : "rounded-full border border-gray-300 px-2 py-1 text-[11px] text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:hover:bg-transparent"}
                  >
                    {chapter.intelligence_available === false ? "Unavailable" : expandedChapter === chapter.number ? "Hide summary" : "Summary"}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => toggleRead(chapter.number, !chapter.read)}
                  className={`text-xs px-2 py-1 rounded-full shrink-0 ${
                    chapter.read
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {chapter.read ? "Mark unread" : "Mark read"}
                </button>
              </div>
              {chapter.intelligence_available === false ? (
                <div className={theme === "dark" ? "mt-3 rounded-xl border border-amber-400/15 bg-amber-400/10 px-3 py-2 text-[11px] text-amber-100" : "mt-3 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-[11px] text-amber-800"}>
                  Chapter text remains available, but AI summaries and advanced tools stop here on the Starter plan.
                </div>
              ) : null}
              {expandedChapter === chapter.number && summaryMap[chapter.number] ? (
                <div className={theme === "dark" ? "mt-4 rounded-xl border border-white/10 bg-white/5 p-4" : "mt-4 rounded-xl border border-gray-200 bg-gray-50 p-4"}>
                  <p className={theme === "dark" ? "text-sm text-gray-100 leading-relaxed whitespace-pre-wrap" : "text-sm text-gray-700 leading-relaxed whitespace-pre-wrap"}>
                    {summaryMap[chapter.number].content}
                  </p>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
