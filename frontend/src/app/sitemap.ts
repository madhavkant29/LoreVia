import type { MetadataRoute } from "next"
import { getAllPublicContentPaths } from "@/lib/content"
import { STATIC_PUBLIC_ROUTES, toAbsoluteUrl } from "@/lib/seo"

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date()
  const staticRoutes = STATIC_PUBLIC_ROUTES.map((path) => ({
    url: toAbsoluteUrl(path),
    lastModified: now,
    changeFrequency: path === "/" ? "weekly" as const : "monthly" as const,
    priority: path === "/" ? 1 : 0.7,
  }))

  const dynamicContentRoutes = getAllPublicContentPaths()
    .filter((path) => !STATIC_PUBLIC_ROUTES.includes(path as (typeof STATIC_PUBLIC_ROUTES)[number]))
    .map((path) => ({
      url: toAbsoluteUrl(path),
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: path.startsWith("/blog/") ? 0.85 : 0.72,
    }))

  return [...staticRoutes, ...dynamicContentRoutes]
}
