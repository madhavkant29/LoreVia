"use client"

import { Suspense } from "react"

import { ChatsPanel } from "@/components/layout/ChatsPanel"

export default function ChatsPage() {
  return (
    <Suspense fallback={null}>
      <ChatsPanel mode="page" />
    </Suspense>
  )
}
