"use client"

import { AuthBootstrap } from "@/components/auth/AuthBootstrap"
import { PWARegister } from "@/components/app/PWARegister"
import { DailyCapPrompt } from "@/components/monetization/DailyCapPrompt"

export function AppRuntime({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AuthBootstrap />
      <DailyCapPrompt />
      <PWARegister />
      {children}
    </>
  )
}
