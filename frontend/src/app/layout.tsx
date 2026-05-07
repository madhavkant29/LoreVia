import type { Metadata, Viewport } from "next"
import "./globals.css"
import { Merriweather, Newsreader, Space_Grotesk } from "next/font/google"
import { AuthBootstrap } from "@/components/auth/AuthBootstrap"
import { PWARegister } from "@/components/app/PWARegister"
import { SiteFooter } from "@/components/layout/SiteFooter"
import { PostHogClientProvider } from "@/components/analytics/PostHogClient"
import {
  DEFAULT_OG_IMAGE,
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_URL,
  organizationJsonLd,
  websiteJsonLd,
} from "@/lib/seo"

const uiFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-ui",
  display: "swap",
})

const merriweather = Merriweather({
  subsets: ["latin"],
  weight: ["400", "700"],
  style: ["normal", "italic"],
  variable: "--font-merriweather",
  display: "swap",
})

const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["400", "600", "800"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
  display: "swap",
})

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: SITE_NAME,
  title: {
    default: "LoreVia: AI Reading Companion for Authors",
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  keywords: [
    "AI writing assistant",
    "manuscript analysis",
    "character tracker",
    "story bible",
    "plot continuity",
    "book writing tool",
    "author tools",
    "LoreVia",
  ],
  authors: [{ name: SITE_NAME, url: SITE_URL }],
  creator: SITE_NAME,
  publisher: SITE_NAME,
  alternates: {
    canonical: "/",
  },
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION || undefined,
    other: process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION
      ? {
          "msvalidate.01": process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION,
        }
      : undefined,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: "LoreVia: AI Reading Companion for Authors",
    description:
      "Track characters, plot threads, timelines and story consistency with AI. Your manuscript, deeply understood.",
    images: [
      {
        url: DEFAULT_OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "LoreVia: AI Reading Companion for Authors",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "LoreVia: AI Reading Companion for Authors",
    description:
      "Track characters, plot threads, timelines and story consistency with AI.",
    images: [DEFAULT_OG_IMAGE],
    creator: "@getlorevia",
  },
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/image.png",
    apple: "/image.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "LoreVia",
  },
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#000000",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${uiFont.variable} ${merriweather.variable} ${newsreader.variable}`}
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
      </head>
      <body className="antialiased">
        <PostHogClientProvider>
          <AuthBootstrap />
          <PWARegister />
          {children}
          <SiteFooter />
        </PostHogClientProvider>
      </body>
    </html>
  )
}
