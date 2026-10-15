// @vitest-environment jsdom

import { renderToStaticMarkup } from "react-dom/server"
import { beforeEach, describe, expect, it, vi } from "vitest"

const navigationState = vi.hoisted(() => ({ pathname: "/public" }))

vi.mock("next/navigation", () => ({ usePathname: () => navigationState.pathname }))
vi.mock("@/components/layout/SiteFooter", () => ({ SiteFooter: () => <footer>Marketing footer</footer> }))

import { PublicSiteFooter } from "./PublicSiteFooter"

describe("PublicSiteFooter", () => {
  beforeEach(() => {
    navigationState.pathname = "/public"
  })

  it("keeps the footer on public catalog and community routes", () => {
    expect(renderToStaticMarkup(<PublicSiteFooter />)).toContain("Marketing footer")
    navigationState.pathname = "/public/forum/post-1"
    expect(renderToStaticMarkup(<PublicSiteFooter />)).toContain("Marketing footer")
  })

  it("removes marketing navigation from a focused chapter reader", () => {
    navigationState.pathname = "/public/ash-gate/chapter/1"
    expect(renderToStaticMarkup(<PublicSiteFooter />)).toBe("")
  })
})
