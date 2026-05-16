"use client"

import Link from "next/link"
import type { Route } from "next"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore, formatWordProgress } from "@/lib/utils/publicForum"
import type { PublicUserProfile } from "@/types/public"

export default function PublicWriterProfilePage() {
  const { username } = useParams<{ username: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: profile = null, isLoading: loading, isError } = useQuery<PublicUserProfile | null>({
    queryKey: asQueryKey(`public:writer:${username}`),
    queryFn: () => publicApi.getUserProfile(username),
  })
  const error = isError ? "Could not load this writer profile." : null

  if (loading) {
    return <div className={`mx-auto max-w-4xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>Loading writer profile...</div>
  }

  if (!profile) {
    return <div className={`mx-auto max-w-4xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>{error || "Writer profile not found."}</div>
  }

  const project = profile.current_project
  const projectHref = project?.source === "public_book" && project.public_book_id
    ? `/public/${project.public_book_id}`
    : project?.source === "forum" && project.forum_post_id
      ? `/public/forum/${project.forum_post_id}`
      : null
  const projectLabel = project?.source === "public_book" ? "Read public sample" : "Open forum discussion"

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#071019] text-slate-100" : "bg-[#f4efe7] text-slate-950"}`}>
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
        <Link href="/public" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>{"<- Back to public library"}</Link>

        <section className={`mt-6 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Public Author Profile</p>
          <h1 className="mt-3 font-serif text-4xl tracking-tight">@{profile.username}</h1>
          <p className={`mt-3 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            This page is an optional public layer around a private author workflow. Reputation and visible activity help show whether this author or collaborator has been thoughtful, reliable, and worth engaging with.
          </p>
          <p className={`mt-3 text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
            Public forum status: public
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Reputation</p>
              <p className="mt-3 font-serif text-4xl">{formatReputationScore(profile.reputation_score)}</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{profile.trust_level}</p>
            </div>
            <div className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Public activity</p>
              <p className="mt-3 text-2xl font-semibold">{profile.forum_post_count} posts</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{profile.forum_comment_count} comments</p>
            </div>
            <div className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Vote history</p>
              <p className="mt-3 text-2xl font-semibold">{profile.reputation_likes_received} likes</p>
              <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{profile.reputation_dislikes_received} dislikes</p>
            </div>
          </div>
        </section>

        <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
          <div className="flex flex-col gap-2">
              <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Surfaced Project</p>
              <h2 className="font-serif text-3xl tracking-tight">{project?.title || "No public sample surfaced yet"}</h2>
          </div>

          {project ? (
            <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_18rem]">
              <div className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
                <div className="flex flex-wrap items-center gap-2">
                  {project.genre ? <span className={`rounded-full px-3 py-1 text-xs font-semibold ${isDark ? "bg-amber-400/15 text-amber-200" : "bg-amber-100 text-amber-800"}`}>{project.genre}</span> : null}
                  <span className={`rounded-full px-3 py-1 text-xs ${isDark ? "bg-white/6 text-slate-300" : "bg-white text-slate-600"}`}>{formatWordProgress(project.progress_words)}</span>
                </div>
                <p className={`mt-5 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{project.description || "This writer has not added a project description yet."}</p>
                {projectHref ? (
                  <Link
                    href={projectHref as Route}
                    className={`mt-5 inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-slate-950 text-white hover:bg-slate-800"}`}
                  >
                    {projectLabel}
                  </Link>
                ) : null}
              </div>
              <div className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Trust snapshot</p>
                <p className="mt-3 text-2xl font-semibold">{profile.trust_level}</p>
                <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                  Use this as lightweight context, not the main product story. LoreVia is still built first for private manuscript work, with public trust signals as an optional add-on.
                </p>
              </div>
            </div>
          ) : (
            <div className={`mt-6 rounded-3xl border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-[#d8c6ab] text-slate-500"}`}>
              This member has not surfaced a sample or manuscript in the public layer yet.
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
