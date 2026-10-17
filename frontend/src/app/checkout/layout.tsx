import Link from "next/link"

import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"

export default function CheckoutLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-[100dvh] bg-[#0b0f14] text-[#f2f4f7]">
      <header className="mx-auto flex max-w-5xl items-center justify-between border-b border-white/10 px-6 py-5">
        <Link href="/" aria-label="LoreVia home">
          <ThemeBrandImage variant="icon" mode="dark" alt="LoreVia" className="h-9 w-9 object-contain" priority />
        </Link>
        <Link href="/pricing" className="text-sm font-medium text-[#a8b0ba] hover:text-white">Pricing</Link>
      </header>
      {children}
    </div>
  )
}
