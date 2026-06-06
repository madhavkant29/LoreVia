import type { Metadata } from "next"
import { AppRuntime } from "@/components/app/AppRuntime"

export const metadata: Metadata = {
  robots: {
    index: false,
    follow: false,
  },
}

export default function ReaderLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppRuntime>
      <div className="app-shell min-h-screen">
        <div className="relative">{children}</div>
      </div>
    </AppRuntime>
  )
}
