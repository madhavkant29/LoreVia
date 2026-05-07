import { NextResponse } from "next/server"
import { getIndexNowKey } from "@/lib/seo"

export function GET() {
  const key = getIndexNowKey()

  if (!key) {
    return new NextResponse("Not Found", {
      status: 404,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
      },
    })
  }

  return new NextResponse(key, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=300",
    },
  })
}
