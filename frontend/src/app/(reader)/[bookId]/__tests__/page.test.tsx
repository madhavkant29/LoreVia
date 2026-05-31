// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

import { RecentActivityCard } from "@/components/overview/RecentActivityCard"

let container: HTMLDivElement | null = null
let root: Root | null = null

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  container = null
  root = null
  document.body.innerHTML = ""
})

function renderActivityCard(isDark = false) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<RecentActivityCard isDark={isDark} />)
  })
}

describe("RecentActivityCard", () => {
  it("shows empty state message when no activity data is available", () => {
    renderActivityCard()

    expect(container?.textContent).toContain(
      "No recent activity yet. Start writing or reading to see your activity here.",
    )
  })

  it("does not render fabricated activity items", () => {
    renderActivityCard()

    expect(container?.textContent).not.toContain("You edited")
    expect(container?.textContent).not.toContain("You updated")
    expect(container?.textContent).not.toContain("World setting updated")
    expect(container?.textContent).not.toContain("Voice consistency check completed")
    expect(container?.textContent).not.toContain("LoreVia checked")
  })

  it("renders the Recent Activity section title", () => {
    renderActivityCard()

    expect(container?.textContent).toContain("Recent Activity")
  })

  it("renders the View All Activity link", () => {
    renderActivityCard()

    expect(container?.textContent).toContain("View All Activity")
  })

  it("renders empty state with dashed border in light mode", () => {
    renderActivityCard(false)

    const emptyState = container?.querySelector(".border-dashed")
    expect(emptyState).toBeTruthy()
  })

  it("renders empty state with dashed border in dark mode", () => {
    renderActivityCard(true)

    const emptyState = container?.querySelector(".border-dashed")
    expect(emptyState).toBeTruthy()
  })
})
