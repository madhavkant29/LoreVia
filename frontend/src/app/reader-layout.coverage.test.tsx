// @vitest-environment jsdom

import { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const navigation = vi.hoisted(() => ({
  bookId: "atlas--123e4567-e89b-12d3-a456-426614174000",
  pathname: "/atlas--123e4567-e89b-12d3-a456-426614174000/manuscript",
  query: new URLSearchParams("mode=write"),
  replace: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: navigation.bookId }),
  usePathname: () => navigation.pathname,
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => navigation.query,
}))

import BookLayout from "@/app/(reader)/[bookId]/layout"

let root: Root | null = null
let container: HTMLDivElement | null = null

async function render(children: ReactNode) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(<BookLayout>{children}</BookLayout>)
    await Promise.resolve()
  })
}

beforeEach(() => {
  navigation.bookId = "atlas--123e4567-e89b-12d3-a456-426614174000"
  navigation.pathname = "/atlas--123e4567-e89b-12d3-a456-426614174000/manuscript"
  navigation.query = new URLSearchParams("mode=write")
  navigation.replace.mockReset()
  sessionStorage.clear()
})

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = null
  container = null
})

describe("reader book layout canonical routing", () => {
  it("replaces a stale route segment from the session cache and preserves query params", async () => {
    sessionStorage.setItem(
      "book-route-segment:123e4567-e89b-12d3-a456-426614174000",
      "atlas-rising--123e4567-e89b-12d3-a456-426614174000",
    )
    await render(<p>Reader child</p>)
    expect(container?.textContent).toBe("Reader child")
    expect(navigation.replace).toHaveBeenCalledWith(
      "/atlas-rising--123e4567-e89b-12d3-a456-426614174000/manuscript?mode=write",
    )
  })

  it("does not replace routes without a different cached canonical segment", async () => {
    navigation.bookId = "plain-book"
    navigation.pathname = "/books/plain-book"
    navigation.query = new URLSearchParams()
    await render(<p>Plain child</p>)
    expect(navigation.replace).not.toHaveBeenCalled()
  })
})
