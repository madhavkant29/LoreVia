import type { Metadata, Viewport } from "next"
import "./globals.css"
import { AuthBootstrap } from "@/components/auth/AuthBootstrap"
import { PWARegister } from "@/components/app/PWARegister"

export const metadata: Metadata = {
  title: "LoreVia - AI Reading Companion",
  description: "Your books, deeply understood.",
  manifest: "/manifest.webmanifest",
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
    <html lang="en">
      <body className="bg-white text-gray-900 antialiased">
        <AuthBootstrap />
        <PWARegister />
        {children}
      </body>
    </html>
  )
}
