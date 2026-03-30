"use client"
import { useState, useEffect } from "react"
import { useReader } from "@/lib/hooks/useReader"
import { ReaderToolbar } from "./ReaderToolbar"
import { ChapterText } from "./ChapterText"
import { ContextPanel } from "./ContextPanel"
import { SummaryPanel } from "./SummaryPanel"

interface Props { bookId: string; chapterNum: number }
type ReaderTheme = "light" | "dark"

export function ReaderView({ bookId, chapterNum }: Props) {
  const { data, loading, error, tap, contextResult, contextLoading, clearContext, saveProgress } = useReader(bookId, chapterNum)
  const [showSummary, setShowSummary] = useState(false)
  const [theme, setTheme] = useState<ReaderTheme>("light")
  const [fontSize, setFontSize] = useState(18)
  const [fontFamily, setFontFamily] = useState<"serif" | "sans" | "mono">("serif")

  useEffect(() => {
    if (data) saveProgress(0)
  }, [data])

  useEffect(() => {
    const storedTheme = window.localStorage.getItem("reader-theme")
    if (storedTheme === "light" || storedTheme === "dark") setTheme(storedTheme)

    const storedSize = window.localStorage.getItem("reader-font-size")
    if (storedSize) setFontSize(parseInt(storedSize))

    const storedFont = window.localStorage.getItem("reader-font-family")
    if (storedFont === "serif" || storedFont === "sans" || storedFont === "mono") setFontFamily(storedFont)

    if (!storedTheme) {
      setTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    }
  }, [])

  useEffect(() => {
    window.localStorage.setItem("reader-theme", theme)
    window.localStorage.setItem("reader-font-size", fontSize.toString())
    window.localStorage.setItem("reader-font-family", fontFamily)
  }, [theme, fontSize, fontFamily])

  const toggleTheme = () => setTheme(current => current === "dark" ? "light" : "dark")

  if (loading) return <div className="flex justify-center py-20 text-gray-400">Loading chapter...</div>
  if (error || !data) return <div className="flex justify-center py-20 text-gray-400">{error ?? "Chapter not found"}</div>

  return (
    <div className={`flex h-screen overflow-hidden transition-colors ${
      theme === "dark" ? "bg-black text-white" : "bg-white text-black"
    }`}>
      <div className="flex-1 flex flex-col overflow-hidden">
        <ReaderToolbar
          bookId={bookId}
          chapterNum={chapterNum}
          totalChapters={null}
          onSummary={() => setShowSummary(true)}
          theme={theme}
          onToggleTheme={toggleTheme}
          fontSize={fontSize}
          onSetFontSize={setFontSize}
          fontFamily={fontFamily}
          onSetFontFamily={setFontFamily}
        />
        <div className="flex-1 overflow-y-auto">
          <ChapterText
            textUrl={data.text_url}
            textContent={data.text_content ?? null}
            characters={data.characters}
            onTap={tap}
            theme={theme}
            fontSize={fontSize}
            fontFamily={fontFamily}
          />
        </div>
      </div>

      {contextResult && (
        <ContextPanel result={contextResult} loading={contextLoading} onClose={clearContext} theme={theme} />
      )}

      {showSummary && (
        <SummaryPanel bookId={bookId} chapterNum={chapterNum} onClose={() => setShowSummary(false)} theme={theme} />
      )}
    </div>
  )
}
