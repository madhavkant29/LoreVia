// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest"

import {
  ActiveIssuesCard,
  CreateFab,
  CurrentProjectCard,
  DailyGoalCard,
  ProjectOverviewCard,
  QuickToolsCard,
  StoryHealthCard,
  WritingStreakCard,
  clickByText,
  clickByTextAsync,
  getContainer,
  renderElement,
} from "./overviewCards.test-utils"

describe("overview cards", () => {
  it("renders the current project card and opens the manuscript editor", async () => {
    const onOpenManuscript = vi.fn()

    await renderElement(
      <CurrentProjectCard
        book={{
          id: "book-1",
          title: "The Ember Gate",
          genre: "Fantasy",
          status: "ready",
          created_at: "2026-01-02T00:00:00Z",
          cover_url: null,
          work_type: "novel",
        } as never}
        isDark={false}
        canOpenManuscript
        currentWords={42000}
        targetWords={80000}
        percentComplete={52}
        chapters={[
          { number: 1, title: "Ash", read: true },
          { number: 2, title: "Gate", read: false },
        ] as never}
        unitTitle="Chapter"
        unitPrefix="Ch."
        onOpenManuscript={onOpenManuscript}
      />,
    )

    expect(getContainer().textContent).toContain("Current Project")
    expect(getContainer().textContent).toContain("The Ember Gate")
    expect(getContainer().textContent).toContain("42,000 / 80,000 words")

    clickByText("Open Manuscript Editor")
    expect(onOpenManuscript).toHaveBeenCalledTimes(1)
  })

  it("renders goal, health, issue, and tool cards with callbacks", async () => {
    const navigate = vi.fn()
    const retry = vi.fn()

    await renderElement(
      <div>
        <DailyGoalCard isDark dailyWords={1250} dailyTarget={1000} />
        <StoryHealthCard
          bookId="book-1"
          isDark={false}
          storyHealth={{
            score: 72,
            status: "Stable",
            summary: "Continuity is mostly intact.",
            metrics: [
              { label: "Continuity", score: 80, detail: "Minor drift." },
              { label: "Pacing", score: 60, detail: "Middle slows." },
            ],
          } as never}
          onRetryStoryHealth={retry}
        />
        <ActiveIssuesCard
          isDark={false}
          continuityIssueCount={2}
          worldGapCount={1}
          timelineIssueCount={0}
          onNavigate={navigate}
          bookId="book-1"
        />
        <QuickToolsCard isDark={false} bookId="book-1" onNavigate={navigate} />
      </div>,
    )

    expect(getContainer().textContent).toContain("Goal reached today.")
    expect(getContainer().textContent).toContain("Story Health")
    expect(getContainer().textContent).toContain("Continuity is mostly intact.")
    expect(getContainer().textContent).toContain("Continuity Flags")
    expect(getContainer().textContent).toContain("Manuscript Editor")

    clickByText("World Gaps")
    clickByText("Story Advisor")
    expect(navigate).toHaveBeenCalledWith("/book-1/world-gap")
    expect(navigate).toHaveBeenCalledWith("/book-1/advisor")
  })

  it("renders project metrics, streaks, and create actions", async () => {
    const addScene = vi.fn()
    const navigate = vi.fn()

    await renderElement(
      <div>
        <ProjectOverviewCard
          isDark={false}
          currentWords={12500}
          chapterCount={8}
          characterCount={14}
          worldArticleCount={6}
        />
        <WritingStreakCard
          isDark
          streakDays={9}
          weekActivity={[true, false, true, true, false, false, true]}
        />
        <CreateFab bookId="book-1" isDark={false} onAddScene={addScene} onNavigate={navigate} />
      </div>,
    )

    expect(getContainer().textContent).toContain("Project Overview")
    expect(getContainer().textContent).toContain("12,500")
    expect(getContainer().textContent).toContain("Sign-in streak")
    expect(getContainer().textContent).toContain("9 days")

    await clickByTextAsync("Create")
    await clickByTextAsync("Add Scene")
    await clickByTextAsync("Create")
    await clickByTextAsync("Add Note")
    await clickByTextAsync("Create")
    await clickByTextAsync("Add Character")

    expect(addScene).toHaveBeenCalledTimes(1)
    expect(navigate).toHaveBeenCalledWith("/book-1/notes")
    expect(navigate).toHaveBeenCalledWith("/book-1/characters")
  })

  it("renders story health retry state", async () => {
    const retry = vi.fn()

    await renderElement(
      <StoryHealthCard
        bookId="book-1"
        isDark
        storyHealth={null}
        storyHealthError
        onRetryStoryHealth={retry}
      />,
    )

    expect(getContainer().textContent).toContain("Failed to load story health")
    clickByText("Retry")
    expect(retry).toHaveBeenCalledTimes(1)
  })

  it("labels story health dimensions without evidence as unavailable", async () => {
    await renderElement(
      <StoryHealthCard
        bookId="book-1"
        isDark={false}
        storyHealth={{
          score: 0,
          status: "Not available",
          summary: "Story health needs analyzed manuscript evidence before a score can be calculated.",
          available: false,
          metrics: [
            { label: "Pacing", score: 0, detail: "At least two chapters are required.", available: false },
          ],
        }}
      />,
    )

    expect(getContainer().textContent).toContain("Not enough data")
    expect(getContainer().textContent).toContain("Unavailable")
    expect(getContainer().textContent).not.toContain("0%")
  })
})
