import type { MetadataRoute } from "next"
import { listPublicBooksServer, listPublicForumPostsServer } from "@/lib/api/public.server"
import { getAllPublicContentEntries } from "@/lib/content"
import { STATIC_PUBLIC_ROUTES, toAbsoluteUrl } from "@/lib/seo"

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date()
  const staticRoutes = STATIC_PUBLIC_ROUTES.map((path) => ({
    url: toAbsoluteUrl(path),
    lastModified: now,
    changeFrequency: path === "/" ? "weekly" as const : "monthly" as const,
    priority: path === "/" ? 1 : 0.7,
  }))

  const dynamicContentRoutes = getAllPublicContentEntries()
    .filter((entry) => !STATIC_PUBLIC_ROUTES.includes(entry.path as (typeof STATIC_PUBLIC_ROUTES)[number]))
    .map((entry) => ({
      url: toAbsoluteUrl(entry.path),
      lastModified: new Date(`${entry.publishedAt}T00:00:00.000Z`),
      changeFrequency: "monthly" as const,
      priority: entry.type === "blog" ? 0.85 : 0.72,
    }))

  const publicBookRoutes = await listPublicBooksServer()
    .then((books) => books.map((book) => ({
      url: toAbsoluteUrl(`/public/${book.public_slug || book.id}`),
      lastModified: new Date(book.created_at ?? now.toISOString()),
      changeFrequency: "weekly" as const,
      priority: 0.76,
    })))
    .catch(() => [])

  const publicForumRoutes = await listPublicForumPostsServer()
    .then((response) => response.items.map((post) => ({
      url: toAbsoluteUrl(`/public/forum/${post.id}`),
      lastModified: new Date(post.updated_at || post.created_at),
      changeFrequency: "weekly" as const,
      priority: 0.64,
    })))
    .catch(() => [])

  return [...staticRoutes, ...dynamicContentRoutes, ...publicBookRoutes, ...publicForumRoutes]
}
