import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query"
import { headers } from "next/headers"
import { serverApi } from "@/lib/api/server"
import { asQueryKey, booksListCacheKey } from "@/lib/query/cacheKeys"
import { LibraryClient } from "./LibraryClient"

export default async function LibraryPage() {
  const cookieHeader = (await headers()).get("cookie") ?? null

  const queryClient = new QueryClient()

  try {
    await queryClient.prefetchQuery({
      queryKey: asQueryKey(booksListCacheKey(true)),
      queryFn: () => serverApi.listBooks(true, cookieHeader),
      staleTime: 20_000,
    })
  } catch {
    // Prefetch failed — let the client fetch it instead
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <LibraryClient />
    </HydrationBoundary>
  )
}
