export const SITE_URL = "https://getlorevia.com"
export const SITE_NAME = "LoreVia"
export const SITE_DESCRIPTION =
  "LoreVia helps authors deeply understand their manuscripts, track characters, plot threads, timelines, and story consistency with AI."
export const DEFAULT_OG_IMAGE = "/og-image.png"

export const STATIC_PUBLIC_ROUTES = [
  "/",
  "/compliance",
  "/contact",
  "/eula",
  "/privacy",
  "/pricing",
  "/refund",
  "/status",
  "/terms",
] as const

export const INDEXNOW_KEY_PATH = "/indexnow-key.txt"

export function toAbsoluteUrl(path: string): string {
  return new URL(path, SITE_URL).toString()
}

export function getIndexNowKey(): string | null {
  const key = process.env.INDEXNOW_KEY?.trim()
  return key ? key : null
}

export function getIndexNowKeyLocation(): string {
  return toAbsoluteUrl(INDEXNOW_KEY_PATH)
}

export const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: SITE_NAME,
  url: SITE_URL,
  description: SITE_DESCRIPTION,
  publisher: {
    "@type": "Organization",
    name: SITE_NAME,
    url: SITE_URL,
    logo: toAbsoluteUrl("/image.png"),
  },
}

export const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: SITE_NAME,
  url: SITE_URL,
  logo: toAbsoluteUrl("/image.png"),
}
