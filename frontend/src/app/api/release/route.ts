import { NextResponse } from "next/server"

import { currentFrontendReleaseSha } from "@/lib/release"

export const dynamic = "force-dynamic"

export function GET() {
  return NextResponse.json(
    {
      app: "LoreVia frontend",
      release_sha: currentFrontendReleaseSha(),
    },
    {
      headers: {
        "Cache-Control": "no-store, max-age=0",
      },
    },
  )
}
