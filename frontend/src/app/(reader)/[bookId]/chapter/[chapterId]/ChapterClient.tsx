"use client"
import { ReaderView } from "@/components/reader/ReaderView"

interface Props {
  bookId: string
  chapterNum: number
}

export function ChapterClient({ bookId, chapterNum }: Props) {
  return <ReaderView bookId={bookId} chapterNum={chapterNum} />
}
