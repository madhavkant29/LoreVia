import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import {
  actionButtonClasses,
  CharacterBibleSkeleton,
  iconButtonClasses,
  OverflowMenu,
  QuickActionTile,
  RelationshipGraphLoading,
  sectionEyebrowClasses,
  ShellIcon,
  StatCard,
  SurfaceCard,
  workspaceActionButtonClasses,
} from "./charactersPage.components"

describe("characters page presentation components", () => {
  it("preserves shared class helpers for light and dark character workspace controls", () => {
    expect(iconButtonClasses(true)).toContain("h-10 w-10")
    expect(iconButtonClasses(false)).toContain("border-stone-200")
    expect(actionButtonClasses(true)).toContain("px-4 py-2.5")
    expect(workspaceActionButtonClasses(true, { active: true, tone: "teal" })).toContain("bg-[#1f615d]")
    expect(sectionEyebrowClasses(false, "amber")).toBe("text-amber-700")
  })

  it("renders skeleton and relationship graph loading states with status labels", () => {
    const bibleMarkup = renderToStaticMarkup(<CharacterBibleSkeleton isDark atmosphere="bg-test" />)
    const graphMarkup = renderToStaticMarkup(<RelationshipGraphLoading />)

    expect(bibleMarkup).toContain("Loading Character Bible")
    expect(bibleMarkup).toContain("bg-test")
    expect(graphMarkup).toContain("Loading relationship graph")
    expect(graphMarkup).toContain("aria-busy=\"true\"")
  })

  it("renders cards, stats, icons, quick actions, and menu actions", () => {
    const surfaceMarkup = renderToStaticMarkup(
      <SurfaceCard title="Identity" isDark={false}>
        <span>Mira</span>
      </SurfaceCard>
    )
    const statMarkup = renderToStaticMarkup(
      <StatCard stat={{ label: "Characters", value: "12", icon: "characters", tone: "violet" }} isDark />
    )
    const iconMarkup = renderToStaticMarkup(<ShellIcon name="repair" />)
    const tileMarkup = renderToStaticMarkup(
      <QuickActionTile isDark title="Find evidence" description="Search scenes." onClick={vi.fn()} icon="search" />
    )
    const menuMarkup = renderToStaticMarkup(
      <OverflowMenu
        isDark={false}
        open
        onToggle={vi.fn()}
        actions={[
          { label: "Export", onClick: vi.fn() },
          { label: "Delete", onClick: vi.fn(), danger: true, dividerBefore: true },
        ]}
      />
    )

    expect(surfaceMarkup).toContain("Identity")
    expect(surfaceMarkup).toContain("Mira")
    expect(statMarkup).toContain("Characters")
    expect(iconMarkup).toContain("viewBox=\"0 0 20 20\"")
    expect(tileMarkup).toContain("Find evidence")
    expect(menuMarkup).toContain("Export")
    expect(menuMarkup).toContain("Delete")
  })
})
