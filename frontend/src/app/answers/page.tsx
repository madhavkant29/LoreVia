import type { Metadata } from "next"

import { AnswerExplorer } from "@/components/content/AnswerExplorer"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { answerPages, getBlogArticleBySlug } from "@/lib/content"
import { SITE_NAME, SITE_URL, buildCollectionPageJsonLd, toAbsoluteUrl } from "@/lib/seo"

const ANSWERS_DESCRIPTION = "Direct, evidence-minded answers to practical questions about drafting, continuity, character work, and fiction revision."

export const metadata: Metadata = {
  title: "Answers",
  description: ANSWERS_DESCRIPTION,
  alternates: { canonical: "/answers" },
  openGraph: {
    title: `Answers from LoreVia Editorial | ${SITE_NAME}`,
    description: ANSWERS_DESCRIPTION,
    url: `${SITE_URL}/answers`,
    images: [{ url: answerPages[0].hero.src, width: 1600, height: 900, alt: answerPages[0].hero.alt }],
  },
  twitter: {
    card: "summary_large_image",
    title: `Answers from LoreVia Editorial | ${SITE_NAME}`,
    description: ANSWERS_DESCRIPTION,
    images: [answerPages[0].hero.src],
  },
}

export default function AnswersPage() {
  const items = answerPages.map((answer) => {
    const parent = getBlogArticleBySlug(answer.articleSlug)
    if (!parent) throw new Error(`Missing parent guide for ${answer.slug}`)
    return {
      slug: answer.slug,
      title: answer.title,
      description: answer.description,
      category: answer.category,
      readTime: answer.readTime,
      parentSlug: parent.slug,
      parentTitle: parent.title,
    }
  })
  const collection = buildCollectionPageJsonLd({
    name: "Answers from LoreVia Editorial",
    description: ANSWERS_DESCRIPTION,
    path: "/answers",
    about: Array.from(new Set(answerPages.map((answer) => answer.category))),
  })
  const itemList = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "LoreVia Editorial answers",
    numberOfItems: answerPages.length,
    itemListElement: answerPages.map((answer, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: toAbsoluteUrl(`/answers/${answer.slug}`),
      name: answer.title,
    })),
  }

  return (
    <PublicContentShell activeSection="answers">
      <JsonLdScript id="answers-collection-jsonld" data={collection} />
      <JsonLdScript id="answers-item-list-jsonld" data={itemList} />
      <div className="editorial-hub editorial-answers-hub">
        <header className="editorial-answers-intro">
          <p className="editorial-kicker">Answers from LoreVia Editorial</p>
          <h1>Start with the question on your desk.</h1>
          <p>{ANSWERS_DESCRIPTION} Every page begins with the useful answer, then shows the reasoning and the revision workflow behind it.</p>
        </header>
        <AnswerExplorer items={items} />
      </div>
    </PublicContentShell>
  )
}
