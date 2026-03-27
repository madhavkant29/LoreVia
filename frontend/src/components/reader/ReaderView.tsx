"use client"
import { useState, useEffect } from "react"
import { useReader } from "@/lib/hooks/useReader"
import { ReaderToolbar } from "./ReaderToolbar"
import { ChapterText } from "./ChapterText"
import { ContextPanel } from "./ContextPanel"
import { SummaryPanel } from "./SummaryPanel"

interface Props { bookId: string; chapterNum: number }

export function ReaderView({ bookId, chapterNum }: Props) {
  const { data, loading, error, tap, contextResult, contextLoading, clearContext, saveProgress } = useReader(bookId, chapterNum)
  const [showSummary, setShowSummary] = useState(false)

  useEffect(() => {
    if (data) saveProgress(0)
  }, [data])

  if (loading) return <div className="flex justify-center py-20 text-gray-400">Loading chapter...</div>
  if (error || !data) return <div className="flex justify-center py-20 text-gray-400">{error ?? "Chapter not found"}</div>

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden">
        <ReaderToolbar
          bookId={bookId}
          chapterNum={chapterNum}
          totalChapters={null}
          onSummary={() => setShowSummary(true)}
        />
        <div className="flex-1 overflow-y-auto">
          <ChapterText
            textUrl={data.text_url}
            textContent={data.text_content ?? null}
            characters={data.characters}
            onTap={tap}
          />
        </div>
      </div>

      {contextResult && (
        <ContextPanel result={contextResult} loading={contextLoading} onClose={clearContext} />
      )}

      {showSummary && (
        <SummaryPanel bookId={bookId} chapterNum={chapterNum} onClose={() => setShowSummary(false)} />
      )}
    </div>
  )
}
