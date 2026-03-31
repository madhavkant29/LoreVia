import type { Metadata } from "next"
import "./globals.css"
import { AuthBootstrap } from "@/components/auth/AuthBootstrap"

export const metadata: Metadata = {
  title: "LoreVia — AI Reading Companion",
  description: "Your books, deeply understood.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900 antialiased">
        <AuthBootstrap />
        {children}
      </body>
    </html>
  )
}
