import { QueryClient } from "@tanstack/react-query"

function matchesQueryString(value: string, matcher: string | RegExp) {
  return typeof matcher === "string" ? value.startsWith(matcher) : matcher.test(value)
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export async function invalidateQueryKeys(matcher: string | RegExp) {
  await queryClient.invalidateQueries({
    predicate: (query) => {
      const [firstKey] = query.queryKey
      return typeof firstKey === "string" && matchesQueryString(firstKey, matcher)
    },
  })
}
