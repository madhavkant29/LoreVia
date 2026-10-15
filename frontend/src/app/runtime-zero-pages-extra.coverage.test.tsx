// @vitest-environment jsdom

import React, { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const pushMock = vi.hoisted(() => vi.fn())
const searchParamsMock = vi.hoisted(() => new URLSearchParams("book=book-1"))
const publicServerMock = vi.hoisted(() => ({ getBook: vi.fn(), getChapter: vi.fn() }))
const jsonLdDataMock = vi.hoisted(() => new Map<string, unknown>())

vi.mock("next/link", () => ({ default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a> }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => searchParamsMock,
  usePathname: () => "/pricing",
}))
vi.mock("next/headers", () => ({ headers: async () => new Headers({ "x-nonce": "nonce-1" }) }))
vi.mock("next/dynamic", () => ({
  default: () => function UploadModalMock(props: { initialExistingBookId: string; onClose: () => void }) {
    return <div>Upload for {props.initialExistingBookId}<button onClick={props.onClose}>Finish upload</button></div>
  },
}))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "dark" }) }))
vi.mock("@/lib/api/public.server", () => ({
  getPublicBookServer: publicServerMock.getBook,
  getPublicChapterServer: publicServerMock.getChapter,
}))
vi.mock("@/components/public/PublicChapterPageClient", () => ({
  PublicChapterPageClient: (props: { bookId: string; chapterId: string; initialChapter: unknown }) => (
    <div data-book={props.bookId} data-chapter={props.chapterId}>Public chapter client {props.initialChapter ? "loaded" : "empty"}</div>
  ),
}))
vi.mock("@/components/seo/JsonLdScript", () => ({
  JsonLdScript: ({ id, data }: { id: string; data: unknown }) => {
    jsonLdDataMock.set(id, data)
    return <script data-testid={id} />
  },
}))
vi.mock("@/components/app/QueryProvider", () => ({ QueryProvider: ({ children }: { children: ReactNode }) => <>{children}</> }))
vi.mock("@/components/billing/PricingPlans", () => ({
  PricingPageIntro: () => <h1>Choose the plan that matches your work</h1>,
  PricingPlans: ({ surface, nonce }: { surface: string; nonce?: string }) => <div>Plans {surface} {nonce}</div>,
}))
vi.mock("@/components/layout/Navbar", () => ({ Navbar: () => <nav>Pricing navigation</nav> }))
vi.mock("@/components/marketing/MarketingHeader", () => ({ MarketingHeader: () => <nav>Pricing navigation</nav> }))

import PublicChapterPage, { generateMetadata } from "./public/[bookId]/chapter/[chapterId]/page"
import PricingPage, { metadata as pricingMetadata } from "./pricing/page"
import UpgradePage, { metadata as upgradeMetadata } from "./(dashboard)/upgrade/page"
import AddChapterPage from "./(dashboard)/library/add-chapter/page"

let root: Root | null = null
let container: HTMLDivElement | null = null

beforeEach(() => {
  pushMock.mockReset()
  jsonLdDataMock.clear()
  publicServerMock.getBook.mockReset().mockResolvedValue({
    id: "book-1",
    public_slug: "gate-draft",
    title: "Gate Draft",
    created_at: "2026-01-01T00:00:00Z",
  })
  publicServerMock.getChapter.mockReset().mockResolvedValue({
    chapter_number: 2,
    chapter_title: "The Key",
    chapter_description: "Mara finds the key.",
  })
})

afterEach(() => {
  if (root) act(() => root?.unmount())
  container?.remove()
  root = null
  container = null
})

describe("previously uncovered runtime pages", () => {
  it("builds public chapter metadata, JSON-LD, loaded and missing page states", async () => {
    const metadata = await generateMetadata({ params: Promise.resolve({ bookId: "gate-draft", chapterId: "2" }) })
    expect(metadata.title).toBe("The Key - Gate Draft")
    expect(metadata.alternates?.canonical).toBe("/public/gate-draft/chapter/2")
    expect(await generateMetadata({ params: Promise.resolve({ bookId: "gate-draft", chapterId: "bad" }) })).toEqual({})

    await render(await PublicChapterPage({ params: Promise.resolve({ bookId: "gate-draft", chapterId: "2" }) }))
    expect(container?.textContent).toContain("Public chapter client loaded")
    expect(container?.querySelectorAll("script")).toHaveLength(2)

    act(() => root?.unmount())
    container?.remove()
    root = null
    container = null
    publicServerMock.getBook.mockRejectedValue(new Error("missing"))
    publicServerMock.getChapter.mockRejectedValue(new Error("missing"))
    expect(await generateMetadata({ params: Promise.resolve({ bookId: "missing", chapterId: "4" }) })).toEqual({})
    await render(await PublicChapterPage({ params: Promise.resolve({ bookId: "missing", chapterId: "4" }) }))
    expect((container as HTMLDivElement | null)?.textContent).toContain("Public chapter client empty")
    expect((container as HTMLDivElement | null)?.querySelectorAll("script")).toHaveLength(0)
  })

  it("renders pricing metadata, structured data, nonce, and plan surface", async () => {
    expect(pricingMetadata.title).toBe("Pricing")
    await render(await PricingPage())
    expect(container?.textContent).toContain("Choose the plan that")
    expect(container?.textContent).toContain("Plans public nonce-1")
    expect(container?.querySelectorAll("script")).toHaveLength(2)
    const pricingJsonLd = jsonLdDataMock.get("pricing-software-jsonld") as {
      offers: Array<{ name: string; price: string }>
    }
    expect(pricingJsonLd.offers.map(({ name, price }) => ({ name, price }))).toEqual([
      { name: "Free", price: "0" },
      { name: "Author Monthly", price: "19" },
      { name: "Author Annual", price: "190" },
      { name: "Architect Monthly", price: "39" },
      { name: "Architect Annual", price: "390" },
    ])
  })

  it("shares the pricing introduction and plan surface on upgrade", async () => {
    expect(upgradeMetadata.title).toBe("Upgrade")
    await render(await UpgradePage())

    expect(container?.textContent).toContain("Choose the plan that matches your work")
    expect(container?.textContent).toContain("Plans app nonce-1")
  })

  it("renders the dark add-chapter flow and returns to the library after upload", async () => {
    await render(<AddChapterPage />)
    expect(container?.textContent).toContain("Add a chapter")
    expect(container?.textContent).toContain("Upload for book-1")
    expect(container?.querySelector('a[href="/book-1/manuscript"]')).not.toBeNull()
    const finish = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent === "Finish upload")
    act(() => finish?.click())
    expect(pushMock).toHaveBeenCalledWith("/library")
  })

  it("keeps chapter import contextual to a selected project", async () => {
    searchParamsMock.delete("book")
    await render(<AddChapterPage />)
    expect(container?.textContent).toContain("Choose a project first")
    expect(container?.textContent).not.toContain("Upload for")
    expect(container?.querySelector('a[href="/library"]')).not.toBeNull()
    searchParamsMock.set("book", "book-1")
  })
})

async function render(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}
