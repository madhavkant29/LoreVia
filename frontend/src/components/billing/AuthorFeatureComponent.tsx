"use client"

import type { ReactNode } from "react"

import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"

type AuthorFeatureComponentProps = {
  children: ReactNode
  locked?: ReactNode
}

export function AuthorFeatureComponent({ children, locked = null }: AuthorFeatureComponentProps) {
  const tier = useAuthStore((state) => state.user?.tier)

  if (tier === "reader") return locked
  if (!canUseAuthorFeatures(tier)) return locked

  return <>{children}</>
}
