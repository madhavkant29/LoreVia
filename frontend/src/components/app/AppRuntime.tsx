"use client"

import dynamic from "next/dynamic"
import { AuthBootstrap } from "@/components/auth/AuthBootstrap"
import { QueryProvider } from "@/components/app/QueryProvider"

const DailyCapPrompt = dynamic(
  () => import("@/components/limits/DailyCapPrompt").then((module) => module.DailyCapPrompt),
  { ssr: false, loading: () => null },
)

const PWARegister = dynamic(
  () => import("@/components/app/PWARegister").then((module) => module.PWARegister),
  { ssr: false, loading: () => null },
)

export function AppRuntime({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <AuthBootstrap />
      <DailyCapPrompt />
      <PWARegister />
      {children}
    </QueryProvider>
  )
}
