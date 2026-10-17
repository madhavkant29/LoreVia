import { vi } from "vitest"

const booksApiMocks = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
  invalidateQueryKeysMock: vi.fn(),
  isAxiosErrorMock: vi.fn(),
}))

const {
  getMock,
  postMock,
  putMock,
  patchMock,
  deleteMock,
  invalidateQueryKeysMock,
  isAxiosErrorMock,
} = booksApiMocks

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    put: putMock,
    patch: patchMock,
    delete: deleteMock,
  },
}))

vi.mock("@/lib/query/queryClient", () => ({
  invalidateQueryKeys: invalidateQueryKeysMock,
}))

vi.mock("axios", () => ({
  default: {
    isAxiosError: isAxiosErrorMock,
  },
  isAxiosError: isAxiosErrorMock,
}))

const { booksApi } = await import("./books")

export { booksApi }

export function resetBooksApiMocks() {
  getMock.mockReset()
  postMock.mockReset()
  putMock.mockReset()
  patchMock.mockReset()
  deleteMock.mockReset()
  invalidateQueryKeysMock.mockReset()
  isAxiosErrorMock.mockReset()

  getMock.mockResolvedValue({ data: { ok: true } })
  postMock.mockResolvedValue({ data: { ok: true } })
  putMock.mockResolvedValue({ data: { ok: true } })
  patchMock.mockResolvedValue({ data: { ok: true } })
  deleteMock.mockResolvedValue({ data: { ok: true } })
}

export {
  deleteMock,
  getMock,
  invalidateQueryKeysMock,
  isAxiosErrorMock,
  patchMock,
  postMock,
  putMock,
}
