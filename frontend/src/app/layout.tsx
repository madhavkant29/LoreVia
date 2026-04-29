import type { Metadata, Viewport } from "next"
import "./globals.css"
import { Inter, Merriweather, Newsreader } from "next/font/google"
import { AuthBootstrap } from "@/components/auth/AuthBootstrap"
import { PWARegister } from "@/components/app/PWARegister"
import { SiteFooter } from "@/components/layout/SiteFooter"

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
  title: "LoreVia - AI Reading Companion",
  description: "Your books, deeply understood.",
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
  themeColor: "#020617",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${merriweather.variable} ${newsreader.variable}`}
    >
      <body className="antialiased">
        <AuthBootstrap />
        <PWARegister />
        {children}
        <SiteFooter />
      </body>
    </html>
  )
}
