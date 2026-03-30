"use client"
import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { readerApi } from "@/lib/api/reader"
import type { ChapterListResponse } from "@/types/reader"

export default function ChapterListPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [data, setData] = useState<ChapterListResponse | null>(null)
  const [theme, setTheme] = useState<"light" | "dark">("light")

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

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${theme === "dark" ? "bg-black text-white" : "bg-white text-black"}`}>
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => router.back()} className={theme === "dark" ? "text-sm text-gray-400 hover:text-white" : "text-sm text-gray-400 hover:text-gray-600"}>{"<- Back"}</button>
          <h1 className="text-2xl font-semibold">Chapters</h1>
          {data && <p className={theme === "dark" ? "text-sm text-gray-400 ml-auto" : "text-sm text-gray-500 ml-auto"}>Current chapter {data.current_chapter ?? data.read_upto}</p>}
        </div>

        <div className="flex flex-col gap-3">
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
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
