export const SITE_URL = "https://getlorevia.com"
export const SITE_NAME = "LoreVia"
export const SITE_TITLE = "LoreVia"
export const SITE_TAGLINE = "LoreVia for authors"
export const SITE_DESCRIPTION =
  "LoreVia for authors turns a manuscript into a searchable story workspace with grounded AI for characters, plot threads, timelines, revisions, and continuity."
export const SITE_LOCALE = "en_US"
export const SITE_LANGUAGE = "en-US"
export const DEFAULT_OG_IMAGE = "/og-image.png"
export const BLOG_RSS_PATH = "/blog/rss.xml"

export const STATIC_PUBLIC_ROUTES = [
  "/",
  "/blog",
  "/answers",
  "/compliance",
  "/contact",
  "/public",
  "/public/forum",
  "/demo",
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

export type BreadcrumbItem = {
  name: string
  path: string
}

export type QuestionAnswerItem = {
  question: string
  answer: string
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
  inLanguage: SITE_LANGUAGE,
  publisher: {
    "@type": "Organization",
    name: SITE_NAME,
    url: SITE_URL,
    logo: toAbsoluteUrl("/logoandtext.png"),
  },
}

export const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: SITE_NAME,
  url: SITE_URL,
  logo: toAbsoluteUrl("/logoandtext.png"),
  sameAs: [
    "https://x.com/getlorevia",
  ],
}

export function buildBreadcrumbJsonLd(items: BreadcrumbItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: toAbsoluteUrl(item.path),
    })),
  }
}

export function buildCollectionPageJsonLd({
  name,
  description,
  path,
  about,
}: {
  name: string
  description: string
  path: string
  about?: string[]
}) {
  return {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name,
    description,
    url: toAbsoluteUrl(path),
    inLanguage: SITE_LANGUAGE,
    about: about?.map((item) => ({
      "@type": "Thing",
      name: item,
    })),
    isPartOf: {
      "@type": "WebSite",
      name: SITE_NAME,
      url: SITE_URL,
    },
  }
}

export function buildFaqPageJsonLd(items: QuestionAnswerItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  }
}

export function buildArticleJsonLd({
  type = "Article",
  title,
  description,
  path,
  datePublished,
  dateModified,
  keywords,
  about,
}: {
  type?: "Article" | "BlogPosting"
  title: string
  description: string
  path: string
  datePublished: string
  dateModified?: string
  keywords?: string[]
  about?: string[]
}) {
  return {
    "@context": "https://schema.org",
    "@type": type,
    headline: title,
    description,
    url: toAbsoluteUrl(path),
    mainEntityOfPage: toAbsoluteUrl(path),
    datePublished,
    dateModified: dateModified ?? datePublished,
    inLanguage: SITE_LANGUAGE,
    keywords,
    about: about?.map((item) => ({
      "@type": "Thing",
      name: item,
    })),
    author: {
      "@type": "Organization",
      name: SITE_NAME,
      url: SITE_URL,
    },
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      url: SITE_URL,
      logo: {
        "@type": "ImageObject",
        url: toAbsoluteUrl("/logoandtext.png"),
      },
    },
    image: [toAbsoluteUrl(DEFAULT_OG_IMAGE)],
  }
}

export function buildProfilePageJsonLd({
  username,
  description,
  path,
}: {
  username: string
  description: string
  path: string
}) {
  return {
    "@context": "https://schema.org",
    "@type": "ProfilePage",
    url: toAbsoluteUrl(path),
    name: `@${username} on ${SITE_NAME}`,
    description,
    inLanguage: SITE_LANGUAGE,
    mainEntity: {
      "@type": "Person",
      name: username,
      alternateName: `@${username}`,
      url: toAbsoluteUrl(path),
    },
    isPartOf: {
      "@type": "WebSite",
      name: SITE_NAME,
      url: SITE_URL,
    },
  }
}

export function buildBookJsonLd({
  title,
  author,
  description,
  path,
  genre,
  chapterCount,
  isAccessibleForFree = true,
}: {
  title: string
  author?: string | null
  description?: string | null
  path: string
  genre?: string | null
  chapterCount?: number | null
  isAccessibleForFree?: boolean
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Book",
    name: title,
    description: description ?? undefined,
    url: toAbsoluteUrl(path),
    inLanguage: SITE_LANGUAGE,
    genre: genre ?? undefined,
    author: author ? { "@type": "Person", name: author } : undefined,
    isAccessibleForFree,
    numberOfPages: chapterCount ?? undefined,
  }
}

export function buildForumThreadJsonLd({
  title,
  body,
  path,
  createdAt,
  updatedAt,
  authorName,
}: {
  title: string
  body: string
  path: string
  createdAt: string
  updatedAt?: string
  authorName: string
}) {
  return {
    "@context": "https://schema.org",
    "@type": "DiscussionForumPosting",
    headline: title,
    articleBody: body,
    url: toAbsoluteUrl(path),
    datePublished: createdAt,
    dateModified: updatedAt ?? createdAt,
    inLanguage: SITE_LANGUAGE,
    author: {
      "@type": "Person",
      name: authorName,
    },
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      url: SITE_URL,
    },
    isPartOf: {
      "@type": "CollectionPage",
      name: `${SITE_NAME} public forum`,
      url: toAbsoluteUrl("/public/forum"),
    },
  }
}

export function buildItemListJsonLd({
  name,
  path,
  items,
}: {
  name: string
  path: string
  items: Array<{ name: string; path: string }>
}) {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name,
    url: toAbsoluteUrl(path),
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      url: toAbsoluteUrl(item.path),
    })),
  }
}
