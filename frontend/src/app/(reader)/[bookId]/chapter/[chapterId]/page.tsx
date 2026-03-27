"use client"
import { useParams } from "next/navigation"
import { ReaderView } from "@/components/reader/ReaderView"

export default function ChapterPage() {
  const { bookId, chapterId } = useParams<{ bookId: string; chapterId: string }>()
  return <ReaderView bookId={bookId} chapterNum={parseInt(chapterId)} />
}
