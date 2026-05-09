import type { MetadataRoute } from "next"
import { STATIC_PUBLIC_ROUTES, toAbsoluteUrl } from "@/lib/seo"

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date()

  return STATIC_PUBLIC_ROUTES.map((path) => ({
    url: toAbsoluteUrl(path),
    lastModified: now,
    changeFrequency: path === "/" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : 0.7,
  }))
}
