// @vitest-environment jsdom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { EditorialCallout, EditorialFigure, EditorialPullQuote, editorialMdxComponents } from "./EditorialMdxComponents"

vi.mock("next/image", () => ({ default: (props: React.ImgHTMLAttributes<HTMLImageElement>) => <img alt={props.alt ?? ""} {...props} /> }))
vi.mock("next/link", () => ({ default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={String(href)} {...props}>{children}</a> }))

afterEach(() => { document.body.innerHTML = "" })

describe("editorial MDX components", () => {
  it("renders accessible figures, callouts, pull quotes, tables, and shared heading anchors", async () => {
    const container = document.createElement("div")
    document.body.appendChild(container)
    const root = createRoot(container)
    const Heading = editorialMdxComponents.h2
    const Table = editorialMdxComponents.table

    await act(async () => root.render(
      <>
        <Heading>Choose the canon</Heading>
        <EditorialCallout title="Editor note">Verify the scene.</EditorialCallout>
        <EditorialPullQuote>Evidence before advice.</EditorialPullQuote>
        <EditorialFigure src="/figure.png" alt="A useful diagram" caption="A caption" />
        <Table><tbody><tr><td>Fact</td></tr></tbody></Table>
      </>,
    ))

    expect(container.querySelector("h2")?.id).toBe("choose-the-canon")
    expect(container.querySelector('aside[aria-label="Editor note"]')).toBeTruthy()
    expect(container.querySelector("blockquote")?.textContent).toContain("Evidence")
    expect(container.querySelector("img")?.getAttribute("alt")).toBe("A useful diagram")
    expect(container.querySelector(".editorial-table-wrap table")).toBeTruthy()
    act(() => root.unmount())
  })
})
