"use client"

import { Suspense } from "react"

import { ManuscriptPageInner } from "./manuscriptPage.inner"

export default function ManuscriptPage() {
  return (
    <Suspense fallback={null}>
      <ManuscriptPageInner />
    </Suspense>
  )
}
