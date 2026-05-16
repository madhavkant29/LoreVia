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
  const latestPublishedAt = [...blogArticles]
    .map((article) => article.publishedAt)
    .sort((left, right) => right.localeCompare(left))[0] ?? "2026-05-14"
  const items = blogArticles
    .map((article) => {
      const articleUrl = toAbsoluteUrl(`/blog/${article.slug}`)
      const description = escapeXml(article.description)
      const title = escapeXml(article.title)

      return `    <item>
      <title>${title}</title>
      <link>${articleUrl}</link>
      <guid>${articleUrl}</guid>
      <pubDate>${new Date(`${article.publishedAt}T00:00:00.000Z`).toUTCString()}</pubDate>
      <description>${description}</description>
    </item>`
    })
    .join("\n")

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${SITE_NAME} Blog</title>
    <link>${toAbsoluteUrl("/blog")}</link>
    <description>Long-form LoreVia guides for fiction authors on continuity, character tracking, story bibles, and manuscript intelligence.</description>
    <language>en-us</language>
    <lastBuildDate>${new Date(`${latestPublishedAt}T00:00:00.000Z`).toUTCString()}</lastBuildDate>
    <generator>${SITE_NAME}</generator>
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
