import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query"
import { headers } from "next/headers"
import { serverApi } from "@/lib/api/server"
import { asQueryKey, booksPageCacheKey } from "@/lib/query/cacheKeys"
import { LibraryClient } from "./LibraryClient"

export default async function LibraryPage() {
  const cookieHeader = (await headers()).get("cookie") ?? null

  const queryClient = new QueryClient()

  try {
    await queryClient.prefetchQuery({
      queryKey: asQueryKey(booksPageCacheKey(true)),
      queryFn: async () => {
        const page = await serverApi.listBooksPage(true, cookieHeader)
        if (page === null) {
          throw new Error("Book prefetch unavailable")
        }
        return page
      },
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
