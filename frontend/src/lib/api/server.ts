import "server-only"

import { resolveApiOrigin } from "@/lib/constants"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type { BookPage } from "./books"
import type { ChapterData } from "@/types/reader"

const API_BASE = `${resolveApiOrigin()}/api/v1`

async function fetchAuthenticatedJson<T>(
  path: string,
  cookieHeader: string | null,
): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      headers: cookieHeader ? { cookie: cookieHeader } : undefined,
    })

    if (response.status === 401 || response.status === 403) {
      return null
    }

    if (!response.ok) {
      throw new Error(`API request failed for ${path} with status ${response.status}`)
    }

    return response.json() as Promise<T>
  } catch {
    return null
  }
}

function readerBookPath(bookId: string, suffix: string) {
  return `/reader/${normalizeBookRouteId(bookId)}${suffix}`
}

export const serverApi = {
  getChapter(bookId: string, chapterNum: number, cookieHeader: string | null) {
    return fetchAuthenticatedJson<ChapterData>(
      `${readerBookPath(bookId, `/chapter/${chapterNum}`)}?include=characters,media,tags,beta_feedback,text_content,html_content,text_url`,
      cookieHeader,
    )
  },

  listBooks(includeHidden: boolean, cookieHeader: string | null) {
    return fetchAuthenticatedJson<BookPage>(
      `/books/page?include_hidden=${includeHidden}&limit=100`,
      cookieHeader,
    ).then((page) => page?.items ?? null)
  },

  listBooksPage(includeHidden: boolean, cookieHeader: string | null) {
    return fetchAuthenticatedJson<BookPage>(
      `/books/page?include_hidden=${includeHidden}&limit=50`,
      cookieHeader,
    )
  },
}
