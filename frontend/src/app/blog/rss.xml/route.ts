import { blogArticles } from "@/lib/content"
import { SITE_NAME, toAbsoluteUrl } from "@/lib/seo"

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;")
}

export async function GET() {
  const publicationArticles = [...blogArticles].sort((left, right) => (
    right.publishedAt.localeCompare(left.publishedAt) || left.order - right.order
  ))
  const latestUpdatedAt = [...blogArticles]
    .map((article) => article.updatedAt)
    .sort((left, right) => right.localeCompare(left))[0] ?? "2026-05-14"
  const items = publicationArticles
    .map((article) => {
      const articleUrl = toAbsoluteUrl(`/blog/${article.slug}`)
      const description = escapeXml(article.description)
      const title = escapeXml(article.title)

      return `    <item>
      <title>${title}</title>
      <link>${articleUrl}</link>
      <guid>${articleUrl}</guid>
      <pubDate>${new Date(`${article.publishedAt}T00:00:00.000Z`).toUTCString()}</pubDate>
      <dc:creator>LoreVia Editorial</dc:creator>
      <category>${escapeXml(article.category)}</category>
      <media:content url="${toAbsoluteUrl(article.hero.src)}" medium="image" width="${article.hero.width}" height="${article.hero.height}" />
      <description>${description}</description>
    </item>`
    })
    .join("\n")

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>${SITE_NAME} Blog</title>
    <link>${toAbsoluteUrl("/blog")}</link>
    <atom:link href="${toAbsoluteUrl("/blog/rss.xml")}" rel="self" type="application/rss+xml" />
    <description>Calm, practical craft and revision guides for fiction authors, published by LoreVia Editorial.</description>
    <language>en-us</language>
    <lastBuildDate>${new Date(`${latestUpdatedAt}T00:00:00.000Z`).toUTCString()}</lastBuildDate>
    <generator>${SITE_NAME} Editorial</generator>
${items}
  </channel>
</rss>`

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      "X-Content-Type-Options": "nosniff",
    },
  })
}
