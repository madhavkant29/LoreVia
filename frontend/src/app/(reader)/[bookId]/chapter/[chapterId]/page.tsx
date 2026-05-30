import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query"
import { headers } from "next/headers"
import { serverApi } from "@/lib/api/server"
import { readerCacheKey } from "@/lib/query/cacheKeys"
import { ChapterClient } from "./ChapterClient"

export default async function ChapterPage({
  params,
}: {
  params: Promise<{ bookId: string; chapterId: string }>
}) {
  const { bookId, chapterId } = await params
  const chapterNum = parseInt(chapterId)
  const cookieHeader = (await headers()).get("cookie") ?? null

  const queryClient = new QueryClient()

  try {
    await queryClient.prefetchQuery({
      queryKey: readerCacheKey(bookId, chapterNum),
      queryFn: () => serverApi.getChapter(bookId, chapterNum, cookieHeader),
      staleTime: 60_000,
    })
  } catch {
    // Prefetch failed — let the client fetch it instead
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <ChapterClient bookId={bookId} chapterNum={chapterNum} />
    </HydrationBoundary>
  )
}
