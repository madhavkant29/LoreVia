"use client"

import Link from "next/link"
import type { Route } from "next"
import { useDeferredValue, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore } from "@/lib/utils/publicForum"
import type { PublicForumPost } from "@/types/public"

export default function PublicForumPage() {
  const [query, setQuery] = useState("")
  const deferredQuery = useDeferredValue(query)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: posts = [], isLoading: loading, isError } = useQuery<PublicForumPost[]>({
    queryKey: asQueryKey(`public:forum:${deferredQuery.trim() || "all"}`),
    queryFn: () => publicApi.listForumPosts(deferredQuery),
  })
  const error = isError ? "Could not load the public forum right now." : null

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#071019] text-slate-100" : "bg-[#f4efe7] text-slate-950"}`}>
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="rounded-[2rem] border px-6 py-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur-sm sm:px-8 lg:px-10">
          <div className={isDark ? "border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.12),transparent_42%)]" : "border-[#d8c6ab] bg-[radial-gradient(circle_at_top_left,rgba(217,119,6,0.12),transparent_42%)]"}>
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Public Beta Forum</p>
            <div className="mt-4 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Find writers, gauge trust, and join the right draft conversation.</h1>
                <p className={`mt-4 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                  Reputation rises when other readers value a person&apos;s comments. Browse active manuscripts, open a discussion, and click through to the writer&apos;s public profile before you commit your time.
                </p>
              </div>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search title, genre, username, or headline"
                className={`h-12 w-full rounded-full border px-5 text-sm outline-none transition lg:max-w-md ${isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500 focus:border-amber-400" : "border-[#d8c6ab] bg-white/90 text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
              />
            </div>
          </div>
        </div>

        {error ? (
          <div className={`mt-6 rounded-3xl border px-5 py-4 text-sm ${isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>{error}</div>
        ) : null}

        <div className="mt-8 grid gap-5">
          {loading ? (
            <div className={`rounded-3xl border px-5 py-6 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-400" : "border-[#dfd3c2] bg-white/90 text-slate-500"}`}>Loading forum posts...</div>
          ) : null}
          {!loading && posts.length === 0 ? (
            <div className={`rounded-3xl border px-5 py-6 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-400" : "border-[#dfd3c2] bg-white/90 text-slate-500"}`}>No public forum posts match this search yet.</div>
          ) : null}
          {!loading ? posts.map((post) => (
            <article key={post.id} className={`rounded-3xl border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em]">
                    <span className={isDark ? "text-amber-300" : "text-amber-700"}>{post.genre || post.work_type}</span>
                    <span className={isDark ? "text-slate-500" : "text-slate-400"}>{new Date(post.created_at).toLocaleDateString()}</span>
                  </div>
                  <h2 className="mt-3 font-serif text-2xl tracking-tight">{post.headline}</h2>
                  <p className={`mt-2 text-base ${isDark ? "text-slate-300" : "text-slate-600"}`}>{post.title}</p>
                  <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{post.body}</p>
                </div>
                <div className={`min-w-[14rem] rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Writer</p>
                  {post.author_username ? (
                    <Link href={`/public/writers/${post.author_username}` as Route} className={`mt-2 block font-semibold ${isDark ? "text-white hover:text-amber-300" : "text-slate-900 hover:text-amber-700"}`}>
                      @{post.author_username}
                    </Link>
                  ) : (
                    <p className="mt-2 font-semibold">{post.author || "Unknown author"}</p>
                  )}
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.author_trust_level} | reputation {formatReputationScore(post.author_reputation_score)}</p>
                  <div className="mt-4 flex flex-wrap gap-2 text-xs">
                    <span className={`rounded-full px-3 py-1 ${isDark ? "bg-white/6 text-slate-300" : "bg-white text-slate-600"}`}>{post.interest_count} interest</span>
                    <span className={`rounded-full px-3 py-1 ${isDark ? "bg-white/6 text-slate-300" : "bg-white text-slate-600"}`}>{post.comment_count} comments</span>
                    <span className={`rounded-full px-3 py-1 ${isDark ? "bg-white/6 text-slate-300" : "bg-white text-slate-600"}`}>Score {Math.round(post.discoverability_score)}</span>
                  </div>
                </div>
              </div>
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Link href={`/public/forum/${post.id}` as Route} className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-slate-950 text-white hover:bg-slate-800"}`}>
                  Open discussion
                </Link>
                <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                  Avg rating {post.rating_summary.average_rating?.toFixed(1) ?? "n/a"} from {post.rating_summary.rating_count} beta review{post.rating_summary.rating_count === 1 ? "" : "s"}.
                </p>
              </div>
            </article>
          )) : null}
        </div>
      </div>
    </div>
  )
}
