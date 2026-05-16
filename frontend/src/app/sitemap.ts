import type { MetadataRoute } from "next"
import { getAllPublicContentEntries } from "@/lib/content"
import { STATIC_PUBLIC_ROUTES, toAbsoluteUrl } from "@/lib/seo"

export default function sitemap(): MetadataRoute.Sitemap {
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

  return [...staticRoutes, ...dynamicContentRoutes]
}
