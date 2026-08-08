import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("@/components/ui/SmartBookCover", () => ({
  SmartBookCover: ({ title }: { title: string }) => <div data-testid="book-cover">{title}</div>,
}))

import { ManuscriptExportMenu as ManuscriptExportMenuComponent } from "@/components/reader/ManuscriptExportMenu"
import { ManuscriptModeSwitch as ManuscriptModeSwitchComponent } from "@/components/reader/ManuscriptModeSwitch"
import { ActiveIssuesCard as ActiveIssuesCardComponent } from "./ActiveIssuesCard"
import { CreateFab as CreateFabComponent } from "./CreateFab"
import { CurrentProjectCard as CurrentProjectCardComponent } from "./CurrentProjectCard"
import { DailyGoalCard as DailyGoalCardComponent } from "./DailyGoalCard"
import { GoalCalendarCard as GoalCalendarCardComponent } from "./GoalCalendarCard"
import { ProjectOverviewCard as ProjectOverviewCardComponent } from "./ProjectOverviewCard"
import { QuickToolsCard as QuickToolsCardComponent } from "./QuickToolsCard"
import { StoryHealthCard as StoryHealthCardComponent } from "./StoryHealthCard"
import { WritingStreakCard as WritingStreakCardComponent } from "./WritingStreakCard"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

export const ActiveIssuesCard = ActiveIssuesCardComponent
export const CreateFab = CreateFabComponent
export const CurrentProjectCard = CurrentProjectCardComponent
export const DailyGoalCard = DailyGoalCardComponent
export const GoalCalendarCard = GoalCalendarCardComponent
export const ManuscriptExportMenu = ManuscriptExportMenuComponent
export const ManuscriptModeSwitch = ManuscriptModeSwitchComponent
export const ProjectOverviewCard = ProjectOverviewCardComponent
export const QuickToolsCard = QuickToolsCardComponent
export const StoryHealthCard = StoryHealthCardComponent
export const WritingStreakCard = WritingStreakCardComponent

export function getContainer() {
  if (!container) throw new Error("Overview card test container is not mounted.")
  return container
}

export async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

export function clickByText(text: string) {
  const button = Array.from(document.body.querySelectorAll<HTMLElement>('button, [role="menuitem"]')).find((item) =>
    item.textContent?.includes(text)
  )
  if (!button) throw new Error(`Missing button: ${text}`)
  act(() => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
  })
}

export async function clickByTextAsync(text: string) {
  const button = Array.from(document.body.querySelectorAll<HTMLElement>('button, [role="menuitem"]')).find((item) =>
    item.textContent?.includes(text)
  )
  if (!button) throw new Error(`Missing button: ${text}`)
  await act(async () => {
    if (button.getAttribute("aria-haspopup") === "menu") {
      button.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, button: 0 }))
    } else {
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    }
    await Promise.resolve()
  })
}

export function setFieldValue(field: HTMLInputElement | HTMLSelectElement, value: string) {
  const prototype = field instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLSelectElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
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
  vi.useRealTimers()
})
