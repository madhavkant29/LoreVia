import { expect, it } from "vitest"
import { graphChapterChoices } from "./graphPage.helpers"

it("offers all available manuscript chapters to authors and only read chapters to readers", () => {
  const chapters = [3, 1, 2, 5, 0].map((number) => ({ number, title: null, processed: true, read: number === 1, intelligence_available: number !== 5 }))
  expect(graphChapterChoices(chapters, true).map((chapter) => chapter.number)).toEqual([1, 2, 3])
  expect(graphChapterChoices(chapters, false).map((chapter) => chapter.number)).toEqual([1])
  expect(chapters[0].number).toBe(3)
  expect(graphChapterChoices([], true)).toEqual([])
})
