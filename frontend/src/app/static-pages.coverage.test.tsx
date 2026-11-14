// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

const jsonLdDataMock = vi.hoisted(() => new Map<string, unknown>())

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/image", () => ({
  default: ({ alt = "", src = "", fill: _fill, priority: _priority, ...props }: { alt?: string; src?: string; fill?: boolean; priority?: boolean }) => <img alt={alt} src={String(src)} {...props} />,
}))

vi.mock("@/components/marketing/ThemeToggle", () => ({
  ThemeToggle: () => <button type="button">Theme</button>,
}))

vi.mock("@/components/seo/JsonLdScript", () => ({
  JsonLdScript: ({ id, data }: { id: string; data: unknown }) => {
    jsonLdDataMock.set(id, data)
    return <script data-testid={id} />
  },
}))

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND")
  },
  usePathname: () => "/",
}))

import HomePage from "./page"
import AnswersPage from "./answers/page"
import BlogPage from "./blog/page"
import CompareIndexPage from "./compare/page"
import CompetitorComparisonPage, { generateMetadata as generateComparisonMetadata, generateStaticParams as generateComparisonStaticParams } from "./compare/[slug]/page"
import CompliancePage from "./compliance/page"
import ContactPage from "./contact/page"
import CopyrightPage from "./copyright/page"
import DemoIndexPage from "./demo/page"
import EulaPage from "./eula/page"
import FontNoticePage from "./font-notice/page"
import RefundPage from "./refund/page"
import StatusPage from "./status/page"
import TermsPage from "./terms/page"
import PrivacyPage from "./privacy/page"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
Object.defineProperty(globalThis, "IntersectionObserver", {
  configurable: true,
  value: class IntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
})
Object.defineProperty(window, "matchMedia", {
  configurable: true,
  value: vi.fn(() => ({
    matches: false,
    media: "",
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
  jsonLdDataMock.clear()
})

describe("static public pages", () => {
  it.each([
    ["home", <HomePage key="home" />, "LoreVia"],
    ["answers", <AnswersPage key="answers" />, "Answers"],
    ["blog", <BlogPage key="blog" />, "Blog"],
    ["compare", <CompareIndexPage key="compare" />, "Compare"],
    ["compliance", <CompliancePage key="compliance" />, "Compliance"],
    ["contact", <ContactPage key="contact" />, "Contact"],
    ["copyright", <CopyrightPage key="copyright" />, "Copyright"],
    ["demo", <DemoIndexPage key="demo" />, "Demo"],
    ["eula", <EulaPage key="eula" />, "End User License"],
    ["font notice", <FontNoticePage key="font-notice" />, "Font"],
    ["refund", <RefundPage key="refund" />, "Refund"],
    ["status", <StatusPage key="status" />, "Status"],
    ["terms", <TermsPage key="terms" />, "Terms"],
    ["privacy", <PrivacyPage key="privacy" />, "Privacy"],
  ])("renders the %s page", async (_name, element, expectedText) => {
    await renderElement(element)

    expect(container?.textContent).toContain(expectedText)
    if (_name === "home") {
      const demoPlayer = container?.querySelector('iframe[title="LoreVia product demonstration"]')
      expect(demoPlayer?.getAttribute("src")).toBe("https://www.youtube-nocookie.com/embed/LVwVqo5X4LA")
      expect(demoPlayer?.getAttribute("loading")).toBe("lazy")
      expect(container?.querySelector('a[href="https://youtu.be/LVwVqo5X4LA"]')?.textContent).toContain("Watch on YouTube")
      const homeJsonLd = jsonLdDataMock.get("home-software-jsonld") as {
        offers: Array<{ name: string; price: string }>
      }
      expect(homeJsonLd.offers.map(({ name, price }) => ({ name, price }))).toEqual([
        { name: "Free", price: "0" },
        { name: "Author Monthly", price: "19" },
        { name: "Author Annual", price: "190" },
        { name: "Architect Monthly", price: "39" },
        { name: "Architect Annual", price: "390" },
      ])
    }
  })

  it("renders a competitor comparison slug page and metadata", async () => {
    const [{ slug }] = await generateComparisonStaticParams()
    const metadata = await generateComparisonMetadata({ params: Promise.resolve({ slug }) })
    const element = await CompetitorComparisonPage({ params: Promise.resolve({ slug }) })

    await renderElement(element)

    expect(metadata.title).toBeTruthy()
    expect(container?.textContent).toContain("Where LoreVia is different")
    expect(container?.textContent).toContain("Choose LoreVia if")
    expect(container?.querySelector("[data-testid='comparison-verdict']")).not.toBeNull()
    expect(container?.querySelector("[data-testid='comparison-table'] table")).not.toBeNull()
    expect(container?.querySelectorAll("[data-testid='comparison-differentiators'] article")).toHaveLength(3)
    expect(container?.querySelector("[data-testid='comparison-differentiators'] .rounded-lg")).toBeNull()
  })

  it("renders comparison destinations as one editorial index without repeated card labels", async () => {
    await renderElement(<CompareIndexPage />)

    const index = container?.querySelector("[data-testid='comparison-index-list']")
    expect(index?.querySelectorAll("a")).toHaveLength(4)
    expect(index?.textContent).not.toContain("Comparison page")
    expect(index?.querySelectorAll("h2")).toHaveLength(4)
  })

  it("renders demos as one source-led catalog without promotional explainer cards", async () => {
    await renderElement(<DemoIndexPage />)

    const index = container?.querySelector("[data-testid='demo-index-list']")
    expect(index?.querySelectorAll("article")).toHaveLength(3)
    expect(index?.textContent).not.toContain("Why these pages matter")
    expect(container?.textContent).not.toContain("SEO angle")
    expect(container?.querySelector('a[href="/demo/workspace"]')).not.toBeNull()
  })

  it("keeps the blog archive complete without repeating artwork in every topic row", async () => {
    await renderElement(<BlogPage />)

    expect(container?.querySelectorAll(".editorial-latest-grid .editorial-story-card__image")).toHaveLength(4)
    expect(container?.querySelectorAll(".editorial-topics img")).toHaveLength(0)
    expect(container?.querySelectorAll(".editorial-archive-list a").length).toBeGreaterThan(0)
  })

  it("returns empty metadata and notFound for unknown comparison slugs", async () => {
    await expect(generateComparisonMetadata({ params: Promise.resolve({ slug: "missing" }) })).resolves.toEqual({})
    await expect(CompetitorComparisonPage({ params: Promise.resolve({ slug: "missing" }) })).rejects.toThrow("NEXT_NOT_FOUND")
  })
})
