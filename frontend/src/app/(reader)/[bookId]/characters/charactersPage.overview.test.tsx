import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { CharacterOverviewIdentityCards } from "./charactersPage.overview"
import { character } from "./charactersPage.testData"

function identityMarkup(citation?: { chapter_number: number; excerpt: string }, addressed?: { chapter_number: number; excerpt: string; attribution_confidence: "contextual" }) {
  return renderToStaticMarkup(
    <CharacterOverviewIdentityCards
      character={character({
        name: "Arun Vale",
        analysis_metadata: {
          ...(citation ? { first_person_self_identification: citation } : {}),
          ...(addressed ? { first_person_addressed_as: addressed } : {}),
        },
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
    expect(identityMarkup()).not.toContain("Narrator clue")
  })

  it("shows a direct address as a tentative clue without claiming narrator identity", () => {
    const markup = identityMarkup(undefined, { chapter_number: 2, excerpt: "you here, Monsieur Vale", attribution_confidence: "contextual" })
    expect(markup).toContain("Narrator clue")
    expect(markup).toContain("This alone does not confirm the first-person narrator")
    expect(markup).not.toContain("Narrator evidence")
  })

  it("shows narrator profile proposals as source-backed suggestions for author review", () => {
    const markup = renderToStaticMarkup(
      <CharacterOverviewIdentityCards
        character={character({
          analysis_metadata: {
            narrator_profile_review: {
              author_confirmed_identity: true,
              generation_id: "generation-1",
              proposals: [{ field: "motivations", value: "find shelter", quote: "I looked for shelter.", chapter_number: 2, source_start: 10, source_end: 31 }],
            },
          },
        })}
        chapterAppearanceText={(chapter) => `Chapter ${chapter}`}
        evidenceCount={0}
        growthEventCount={0}
        isDark={false}
        knownFacts={[]}
        reviewStatus="Pending review"
        summary=""
        onOpenEvidence={() => {}}
        onAcceptNarratorClaim={() => {}}
      />,
    )
    expect(markup).toContain("Narrator profile suggestions")
    expect(markup).toContain("find shelter")
    expect(markup).toContain("I looked for shelter.")
    expect(markup).toContain("Accept claim")
  })

  it("shows named-person profile proposals without claiming narrator identity", () => {
    const markup = renderToStaticMarkup(
      <CharacterOverviewIdentityCards
        character={character({
          analysis_metadata: {
            character_profile_review: {
              subject_mode: "named_person",
              generation_id: "generation-1",
              proposals: [{ field: "personality_tags", value: "helpful", quote: "Mara lifted the gate.", chapter_number: 1, source_start: 0, source_end: 21 }],
            },
          },
        })}
        chapterAppearanceText={(chapter) => `Chapter ${chapter}`}
        evidenceCount={0}
        growthEventCount={0}
        isDark={false}
        knownFacts={[]}
        reviewStatus="Pending review"
        summary=""
        onOpenEvidence={() => {}}
        onAcceptNarratorClaim={() => {}}
      />,
    )
    expect(markup).toContain("Character profile suggestions")
    expect(markup).not.toContain("First-person identity was confirmed")
    expect(markup).toContain("Mara lifted the gate.")
  })
})
