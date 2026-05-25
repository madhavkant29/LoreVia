import { beforeEach, describe, expect, it, vi } from "vitest"

const useQueryMock = vi.hoisted(() => vi.fn())
const useQueryClientMock = vi.hoisted(() => vi.fn())
const getMock = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useQueryClient: useQueryClientMock,
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    get: getMock,
  },
}))

import { useCachedBookDetail } from "./useBookDetail"

describe("useCachedBookDetail", () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    useQueryClientMock.mockReset()
    getMock.mockReset()
    useQueryMock.mockReturnValue({ data: null })
  })

  it("does not seed the shared detail query with null when nothing is cached", () => {
    useQueryClientMock.mockReturnValue({
      getQueryData: vi.fn(() => undefined),
    })

    useCachedBookDetail("book-1")

    expect(useQueryMock).toHaveBeenCalledTimes(1)
    const options = useQueryMock.mock.calls[0]?.[0] as { initialData: () => unknown }
    expect(options.initialData()).toBeUndefined()
  })

  it("reuses an existing cached book detail when one is present", () => {
    const cachedBook = { id: "book-1", title: "Sky of Ash" }
    useQueryClientMock.mockReturnValue({
      getQueryData: vi.fn(() => cachedBook),
    })

    useCachedBookDetail("book-1")

    const options = useQueryMock.mock.calls[0]?.[0] as { initialData: () => unknown }
    expect(options.initialData()).toBe(cachedBook)
  })
})
