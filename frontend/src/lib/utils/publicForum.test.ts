import { describe, expect, it } from "vitest"

import type { Book } from "@/types/book"
import type { PublicForumPost } from "@/types/public"

import {
  formatReputationScore,
  formatWordProgress,
  getEligibleForumAuthorBooks,
  isEligibleForumAuthorBook,
} from "./publicForum"

describe("public forum utilities", () => {
  it("formats positive reputation scores with a leading plus", () => {
    expect(formatReputationScore(7)).toBe("+7")
    expect(formatReputationScore(-3)).toBe("-3")
    expect(formatReputationScore(0)).toBe("0")
  })

  it("formats word progress using compact thousand labels", () => {
    expect(formatWordProgress(987)).toBe("987 words")
    expect(formatWordProgress(1200)).toBe("1.2k words")
    expect(formatWordProgress(20000)).toBe("20k words")
  })

  it("treats private drafts and approved public shares as forum eligible", () => {
    const privateDraft = { id: "private", mode: "author", is_public: false, hidden_at: null, archived_at: null } as Book
    const approvedPublicShare = {
      id: "public-share",
      mode: "author",
      is_public: true,
      source_kind: "user_public_share",
      public_share_status: "approved",
      hidden_at: null,
      archived_at: null,
    } as Book

    expect(isEligibleForumAuthorBook(privateDraft)).toBe(true)
    expect(isEligibleForumAuthorBook(approvedPublicShare)).toBe(true)
  })

  it("excludes non-author books, hidden books, and pending public shares from forum eligibility", () => {
    const readerBook = { id: "reader", mode: "reader", is_public: false, hidden_at: null, archived_at: null } as Book
    const hiddenDraft = { id: "hidden", mode: "author", is_public: false, hidden_at: "2026-05-18T00:00:00Z", archived_at: null } as Book
    const pendingPublicShare = {
      id: "pending",
      mode: "author",
      is_public: true,
      source_kind: "user_public_share",
      public_share_status: "pending",
      hidden_at: null,
      archived_at: null,
    } as Book

    expect(isEligibleForumAuthorBook(readerBook)).toBe(false)
    expect(isEligibleForumAuthorBook(hiddenDraft)).toBe(false)
    expect(isEligibleForumAuthorBook(pendingPublicShare)).toBe(false)
  })

  it("filters out books that already have an open forum discussion", () => {
    const books = [
      { id: "book-1", mode: "author", is_public: false, hidden_at: null, archived_at: null },
      { id: "book-2", mode: "author", is_public: false, hidden_at: null, archived_at: null },
    ] as Book[]
    const myForumPosts = [
      { id: "post-1", book_id: "book-1", status: "open" },
      { id: "post-2", book_id: "book-2", status: "closed" },
    ] as PublicForumPost[]

    expect(getEligibleForumAuthorBooks(books, myForumPosts).map((book) => book.id)).toEqual(["book-2"])
  })
})
