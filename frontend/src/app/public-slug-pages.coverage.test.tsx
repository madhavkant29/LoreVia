// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND")
  },
}))

vi.mock("@/components/marketing/PublicContentHeader", () => ({
  ContentArrowIcon: () => <span aria-hidden="true">arrow</span>,
}))

vi.mock("@/components/marketing/PublicContentShell", () => ({
  PublicContentShell: ({ children, activeSection }: { children: ReactNode; activeSection: string }) => (
    <main data-active-section={activeSection}>{children}</main>
  ),
}))

vi.mock("@/components/seo/JsonLdScript", () => ({
  JsonLdScript: ({ id }: { id: string; data: unknown }) => <script data-testid={id} />,
}))

import AnswerPage, {
  generateMetadata as generateAnswerMetadata,
  generateStaticParams as generateAnswerStaticParams,
} from "@/app/answers/[slug]/page"
import BlogArticlePage, {
  generateMetadata as generateBlogMetadata,
  generateStaticParams as generateBlogStaticParams,
} from "@/app/blog/[slug]/page"
import DemoPage, {
  generateMetadata as generateDemoMetadata,
  generateStaticParams as generateDemoStaticParams,
} from "@/app/demo/[slug]/page"
import { answerPages, blogArticles, demoPages } from "@/lib/content"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

function bodyText() {
  return container?.textContent ?? ""
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
})

describe("public slug runtime pages", () => {
  it("renders blog, demo, and answer slug pages with generated metadata", async () => {
    const article = blogArticles[0]
    const demo = demoPages[0]
    const answer = answerPages[0]

    expect(generateBlogStaticParams()).toContainEqual({ slug: article.slug })
    expect(generateDemoStaticParams()).toContainEqual({ slug: demo.slug })
    expect(generateAnswerStaticParams()).toContainEqual({ slug: answer.slug })

    await renderElement(await BlogArticlePage({ params: Promise.resolve({ slug: article.slug }) }))
    expect(bodyText()).toContain(article.title)
    expect(bodyText()).toContain(article.description)
    expect(container?.querySelector("main")?.getAttribute("data-active-section")).toBe("blog")
    expect(container?.querySelector(`[data-testid="blog-jsonld-${article.slug}"]`)).toBeTruthy()

    root?.unmount()
    container?.remove()
    root = null
    container = null

    await renderElement(await DemoPage({ params: Promise.resolve({ slug: demo.slug }) }))
    expect(bodyText()).toContain(demo.title)
    expect(bodyText()).toContain(demo.featuredInsight)
    expect(container?.querySelector("main")?.getAttribute("data-active-section")).toBe("demo")
    expect(container?.querySelector(`[data-testid="demo-jsonld-${demo.slug}"]`)).toBeTruthy()

    root?.unmount()
    container?.remove()
    root = null
    container = null

    await renderElement(await AnswerPage({ params: Promise.resolve({ slug: answer.slug }) }))
    expect(bodyText()).toContain(answer.question)
    expect(bodyText()).toContain(answer.shortAnswer)
    expect(container?.querySelector("main")?.getAttribute("data-active-section")).toBe("answers")
    expect(container?.querySelector(`[data-testid="answers-jsonld-${answer.slug}"]`)).toBeTruthy()

    const blogMetadata = await generateBlogMetadata({ params: Promise.resolve({ slug: article.slug }) })
    const demoMetadata = await generateDemoMetadata({ params: Promise.resolve({ slug: demo.slug }) })
    const answerMetadata = await generateAnswerMetadata({ params: Promise.resolve({ slug: answer.slug }) })

    expect(blogMetadata.title).toBe(article.title)
    expect(demoMetadata.title).toBe(demo.title)
    expect(answerMetadata.title).toBe(answer.question)
  })

  it("returns empty metadata and raises notFound for unknown slugs", async () => {
    await expect(generateBlogMetadata({ params: Promise.resolve({ slug: "missing-blog" }) })).resolves.toEqual({})
    await expect(generateDemoMetadata({ params: Promise.resolve({ slug: "missing-demo" }) })).resolves.toEqual({})
    await expect(generateAnswerMetadata({ params: Promise.resolve({ slug: "missing-answer" }) })).resolves.toEqual({})

    await expect(BlogArticlePage({ params: Promise.resolve({ slug: "missing-blog" }) })).rejects.toThrow("NEXT_NOT_FOUND")
    await expect(DemoPage({ params: Promise.resolve({ slug: "missing-demo" }) })).rejects.toThrow("NEXT_NOT_FOUND")
    await expect(AnswerPage({ params: Promise.resolve({ slug: "missing-answer" }) })).rejects.toThrow("NEXT_NOT_FOUND")
  })
})
