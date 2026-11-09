import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { CharacterOverviewIdentityCards } from "./charactersPage.overview"
import { character } from "./charactersPage.testData"

function identityMarkup(citation?: { chapter_number: number; excerpt: string }) {
  return renderToStaticMarkup(
    <CharacterOverviewIdentityCards
      character={character({
        name: "Arun Vale",
        analysis_metadata: citation ? { first_person_self_identification: citation } : {},
      })}
      chapterAppearanceText={(chapter) => `Chapter ${chapter}`}
      evidenceCount={0}
      growthEventCount={0}
      isDark={false}
      knownFacts={[]}
      reviewStatus="Pending review"
      summary=""
      totalChapters={3}
      onOpenEvidence={() => {}}
    />,
  )
}

describe("CharacterOverviewIdentityCards narrator evidence", () => {
  it("shows cited first-person self-identification as tentative narrator evidence", () => {
    const markup = identityMarkup({ chapter_number: 2, excerpt: "I told her I was Arun Vale" })
    expect(markup).toContain("Narrator evidence")
    expect(markup).toContain("Possible first-person self-identification, Chapter 2")
    expect(markup).toContain("I told her I was Arun Vale")
  })

  it("does not suggest a narrator without source evidence", () => {
    expect(identityMarkup()).not.toContain("Narrator evidence")
  })
})
