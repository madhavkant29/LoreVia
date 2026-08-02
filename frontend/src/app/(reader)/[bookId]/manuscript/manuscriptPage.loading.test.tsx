import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import {
  BookOpenIcon,
  DeferredPanelLoadingState,
  InlineLoadingRows,
  ManuscriptEditorSkeleton,
} from "./manuscriptPage.loading"

describe("manuscript page loading components", () => {
  it("renders reusable loading states with stable labels and theme classes", () => {
    const skeletonMarkup = renderToStaticMarkup(<ManuscriptEditorSkeleton isDark />)
    const panelMarkup = renderToStaticMarkup(<DeferredPanelLoadingState label="Loading writing tools..." />)
    const rowsMarkup = renderToStaticMarkup(<InlineLoadingRows isDark={false} label="Loading annotations" rows={2} />)

    expect(skeletonMarkup).toContain("bg-[#101416]")
    expect(skeletonMarkup).toContain("xl:grid-cols-[22rem_minmax(0,1fr)_23.5rem]")
    expect(panelMarkup).toContain("Loading writing tools...")
    expect(rowsMarkup).toContain("role=\"status\"")
    expect(rowsMarkup).toContain("Loading annotations")
  })

  it("renders the book icon as hidden decorative SVG", () => {
    const markup = renderToStaticMarkup(<BookOpenIcon />)

    expect(markup).toContain("aria-hidden=\"true\"")
    expect(markup).toContain("viewBox=\"0 0 24 24\"")
  })
})
