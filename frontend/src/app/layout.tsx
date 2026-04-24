import type { Metadata, Viewport } from "next"
import "./globals.css"
import { Inter, Merriweather, Newsreader } from "next/font/google"
import { AuthBootstrap } from "@/components/auth/AuthBootstrap"
import { PWARegister } from "@/components/app/PWARegister"
import { SiteFooter } from "@/components/layout/SiteFooter"
import { PostHogClientProvider } from "@/components/analytics/PostHogClient"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
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
  metadataBase: new URL("https://getlorevia.com"),
  title: {
    default: "LoreVia — AI Reading Companion for Authors",
    template: "%s | LoreVia",
  },
  description:
    "LoreVia helps authors deeply understand their manuscripts — track characters, plot threads, timelines, and story consistency with AI.",
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
  authors: [{ name: "LoreVia", url: "https://getlorevia.com" }],
  creator: "LoreVia",
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://getlorevia.com",
    siteName: "LoreVia",
    title: "LoreVia — AI Reading Companion for Authors",
    description:
      "Track characters, plot threads, timelines and story consistency with AI. Your manuscript, deeply understood.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "LoreVia — AI Reading Companion for Authors",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "LoreVia — AI Reading Companion for Authors",
    description:
      "Track characters, plot threads, timelines and story consistency with AI.",
    images: ["/og-image.png"],
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
      className={`${inter.variable} ${merriweather.variable} ${newsreader.variable}`}
    >
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
