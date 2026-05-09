import type { Book } from "@/types/book"

const UUID_PATTERN = /[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function normalizeBookRouteId(routeBookId: string): string {
  const trimmed = routeBookId.trim()
  const parts = trimmed.split("--")
  const candidate = parts[parts.length - 1] ?? trimmed
  return UUID_PATTERN.test(candidate) ? candidate : trimmed
}

export function slugifyBookTitle(title: string): string {
  const normalized = title
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")

  return normalized || "project"
}

export function getBookRouteSegment(book: Pick<Book, "id" | "title">): string {
  return `${slugifyBookTitle(book.title)}--${book.id}`
}

export function getBookHref(book: Pick<Book, "id" | "title">, suffix = ""): string {
  return `/${getBookRouteSegment(book)}${suffix}`
}

export function replaceBookRouteSegment(pathname: string, currentSegment: string, nextSegment: string): string {
  const currentPrefix = `/${currentSegment}`
  if (!pathname.startsWith(currentPrefix)) return pathname
  return `/${nextSegment}${pathname.slice(currentPrefix.length)}`
}
