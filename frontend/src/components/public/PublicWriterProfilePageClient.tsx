"use client"

import Link from "next/link"
import type { Route } from "next"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore, formatWordProgress } from "@/lib/utils/publicForum"
import type { PublicBook } from "@/types/book"
import type { PublicUserActivityComment, PublicUserActivityPost, PublicUserProfile } from "@/types/public"

function formatCompactDate(value?: string | null) {
  if (!value) return "Not yet dated"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Not yet dated"
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

export function PublicWriterProfilePageClient({
  username,
  initialProfile = null,
}: {
  username: string
  initialProfile?: PublicUserProfile | null
}) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [activeTab, setActiveTab] = useState<"posts" | "comments">("posts")
  const { data: profile = initialProfile, isLoading: loading, isError } = useQuery<PublicUserProfile | null>({
    queryKey: asQueryKey(`public:writer:${username}`),
    queryFn: () => publicApi.getUserProfile(username),
    initialData: initialProfile,
  })
  const error = isError ? "Could not load this writer profile." : null

  if (loading) {
    return <div className={`mx-auto max-w-4xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>Loading writer profile...</div>
  }

  if (!profile) {
    return <div className={`mx-auto max-w-4xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>{error || "Writer profile not found."}</div>
  }

  const project = profile.current_project
  const publicSampleHref = project?.public_book_id ? `/public/${project.public_book_id}` : null
  const forumDiscussionHref = project?.forum_post_id ? `/public/forum/${project.forum_post_id}` : null

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#0a1016] text-slate-100" : "bg-[#f4efe7] text-slate-950"}`}>
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <Link href="/public" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>{"<- Back to public library"}</Link>

        <section className={`mt-6 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-[#121821]" : "border-[#dfd3c2] bg-white/92"}`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Public Writer Profile</p>
              <h1 className="mt-3 font-serif text-4xl tracking-tight">@{profile.username}</h1>
              <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                Visible public profile for reading activity, discussion history, and the public books this writer has chosen to share.
              </p>
              <p className={`mt-3 text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                Public forum status: public
              </p>
            </div>
            <Link
              href={`/chats?username=${encodeURIComponent(profile.username)}` as Route}
              className={`inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
            >
              Message @{profile.username}
            </Link>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3 xl:grid-cols-6">
            <ProfileStat isDark={isDark} label="Reputation" value={formatReputationScore(profile.reputation_score)} detail={profile.trust_level} />
            <ProfileStat isDark={isDark} label="Posts" value={String(profile.forum_post_count)} detail="Visible threads" />
            <ProfileStat isDark={isDark} label="Comments" value={String(profile.forum_comment_count)} detail="Visible replies" />
            <ProfileStat isDark={isDark} label="Votes" value={`${profile.reputation_likes_received}/${profile.reputation_dislikes_received}`} detail="likes / dislikes" />
            <ProfileStat isDark={isDark} label="Views" value={profile.public_analytics.total_book_views.toLocaleString()} detail="Across public books" />
            <ProfileStat isDark={isDark} label="Readers 30d" value={profile.public_analytics.total_unique_readers_30d.toLocaleString()} detail="Distinct recent visitors" />
          </div>
        </section>

        <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-[#121821]" : "border-[#dfd3c2] bg-white/92"}`}>
          <div className="flex flex-col gap-2">
            <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Public upload analytics</p>
            <h2 className="font-serif text-3xl tracking-tight">Visible public footprint</h2>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <ProfileStat isDark={isDark} label="Public books" value={String(profile.public_books_count)} detail="Visible creator-published books" />
            <ProfileStat isDark={isDark} label="Chapters" value={String(profile.public_analytics.total_chapters)} detail="Visible public chapters" />
            <ProfileStat isDark={isDark} label="Words" value={formatWordProgress(profile.public_analytics.total_words)} detail="Estimated readable words" />
            <ProfileStat isDark={isDark} label="Latest published" value={formatCompactDate(profile.public_analytics.latest_published_at)} detail="Most recent dated upload" />
            <ProfileStat isDark={isDark} label="Open discussions" value={String(profile.public_analytics.open_forum_discussions_count)} detail="Active public forum threads" />
          </div>
        </section>

        <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-[#121821]" : "border-[#dfd3c2] bg-white/92"}`}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Public books</p>
              <h2 className="font-serif text-3xl tracking-tight">Books published by @{profile.username}</h2>
            </div>
            <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{profile.public_books_count} visible upload{profile.public_books_count === 1 ? "" : "s"}</p>
          </div>

          {profile.public_books.length > 0 ? (
            <div className="mt-6 grid gap-5 lg:grid-cols-2">
              {profile.public_books.map((book) => (
                <PublicBookCard key={book.id} isDark={isDark} book={book} />
              ))}
            </div>
          ) : (
            <EmptyState isDark={isDark} text="This writer has not surfaced any visible creator-published public books yet." />
          )}
        </section>

        <section className={`mt-8 rounded-[2rem] border ${isDark ? "border-white/10 bg-[#121821]" : "border-[#dfd3c2] bg-white/92"}`}>
          <div className={`flex flex-wrap items-center justify-between gap-4 border-b px-6 py-5 ${isDark ? "border-white/10" : "border-[#eadfce]"}`}>
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Activity</p>
              <h2 className="mt-2 font-serif text-3xl tracking-tight">Discussion history</h2>
            </div>
            <div className={`inline-flex rounded-full p-1 ${isDark ? "bg-white/[0.05]" : "bg-[#f7f0e5]"}`}>
              <TabButton isDark={isDark} active={activeTab === "posts"} onClick={() => setActiveTab("posts")} label={`Posts (${profile.posts.length})`} />
              <TabButton isDark={isDark} active={activeTab === "comments"} onClick={() => setActiveTab("comments")} label={`Comments (${profile.comments.length})`} />
            </div>
          </div>

          <div className="p-4 sm:p-6">
            {activeTab === "posts" ? (
              <div className="space-y-4">
                {profile.posts.length === 0 ? (
                  <EmptyState isDark={isDark} text="No public posts are visible for this writer yet." />
                ) : profile.posts.map((post) => (
                  <PostActivityCard key={post.id} isDark={isDark} post={post} />
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                {profile.comments.length === 0 ? (
                  <EmptyState isDark={isDark} text="No public comments are visible for this writer yet." />
                ) : profile.comments.map((comment) => (
                  <CommentActivityCard key={comment.id} isDark={isDark} comment={comment} />
                ))}
              </div>
            )}
          </div>
        </section>

        <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-[#121821]" : "border-[#dfd3c2] bg-white/92"}`}>
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
                {forumDiscussionHref || publicSampleHref ? (
                  <div className="mt-5 flex flex-wrap gap-3">
                    {forumDiscussionHref ? (
                      <Link
                        href={forumDiscussionHref as Route}
                        className={`inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-slate-950 text-white hover:bg-slate-800"}`}
                      >
                        Open forum discussion
                      </Link>
                    ) : null}
                    {publicSampleHref ? (
                      <Link
                        href={publicSampleHref as Route}
                        className={`inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
                      >
                        Read public sample
                      </Link>
                    ) : null}
                  </div>
                ) : null}
              </div>
              <div className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Public reach</p>
                <p className="mt-3 text-2xl font-semibold">{profile.public_analytics.total_chapter_views.toLocaleString()}</p>
                <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                  Chapter opens across this writer&apos;s visible public uploads.
                </p>
              </div>
            </div>
          ) : (
            <EmptyState isDark={isDark} text="This member has not surfaced a sample or manuscript in the public layer yet." />
          )}
        </section>
      </div>
    </div>
  )
}

function ProfileStat({ isDark, label, value, detail }: { isDark: boolean, label: string, value: string, detail: string }) {
  return (
    <div className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>{label}</p>
      <p className="mt-3 text-2xl font-semibold">{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{detail}</p>
    </div>
  )
}

function TabButton({ isDark, active, onClick, label }: { isDark: boolean, active: boolean, onClick: () => void, label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-2 text-sm font-semibold transition ${active ? (isDark ? "bg-amber-400 text-slate-950" : "bg-slate-950 text-white") : (isDark ? "text-slate-300 hover:bg-white/10" : "text-slate-700 hover:bg-white")}`}
    >
      {label}
    </button>
  )
}

function PublicBookCard({ isDark, book }: { isDark: boolean; book: PublicBook }) {
  return (
    <article className={`rounded-3xl border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]">
        <span className={isDark ? "text-cyan-300" : "text-cyan-700"}>{book.genre || "Unspecified genre"}</span>
        <span className={isDark ? "text-slate-500" : "text-slate-500"}>&bull;</span>
        <span className={isDark ? "text-slate-400" : "text-slate-500"}>{formatCompactDate(book.published_at)}</span>
      </div>
      <Link href={`/public/${book.public_slug || book.id}` as Route} className="mt-3 block text-2xl font-semibold hover:underline">
        {book.title}
      </Link>
      {book.description ? <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{book.description}</p> : null}
      <div className={`mt-4 flex flex-wrap gap-3 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>
        <span>{book.total_chapters ?? 0} chapters</span>
        <span>{book.analytics?.book_view_count?.toLocaleString?.() ?? 0} views</span>
      </div>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link href={`/public/${book.public_slug || book.id}` as Route} className={`inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white text-slate-950 hover:bg-slate-200" : "bg-slate-950 text-white hover:bg-slate-800"}`}>
          Read public book
        </Link>
        {book.active_forum_post_id ? (
          <Link href={`/public/forum/${book.active_forum_post_id}` as Route} className={`inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}>
            Open discussion
          </Link>
        ) : null}
      </div>
    </article>
  )
}

function PostActivityCard({ isDark, post }: { isDark: boolean, post: PublicUserActivityPost }) {
  const href = `/public/forum/${post.id}` as Route
  const typeLabel = post.thread_type === "general" ? "General" : "Novel"
  const statusLabel = post.status === "open" ? "Open" : "Closed"

  return (
    <article className={`rounded-3xl border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]">
        <span className={`${isDark ? "text-cyan-300" : "text-cyan-700"}`}>{typeLabel}</span>
        <span className={isDark ? "text-slate-500" : "text-slate-500"}>&bull;</span>
        <span className={post.status === "open" ? (isDark ? "text-emerald-300" : "text-emerald-700") : (isDark ? "text-slate-400" : "text-slate-500")}>{statusLabel}</span>
      </div>
      <Link href={href} className="mt-3 block text-2xl font-semibold hover:underline">{post.headline}</Link>
      {post.title ? <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.title}</p> : null}
      <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{post.body}</p>
      <div className={`mt-4 flex flex-wrap gap-3 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>
        <span>{post.comment_count} comments</span>
        <span>{post.interest_count} reader notes</span>
        <span>{post.like_count} likes</span>
        <span>{post.dislike_count} dislikes</span>
      </div>
    </article>
  )
}

function CommentActivityCard({ isDark, comment }: { isDark: boolean, comment: PublicUserActivityComment }) {
  return (
    <article className={`rounded-3xl border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]">
        <span className={comment.thread_type === "general" ? (isDark ? "text-cyan-300" : "text-cyan-700") : (isDark ? "text-amber-300" : "text-amber-700")}>
          {comment.thread_type === "general" ? "General" : "Novel"}
        </span>
        <span className={isDark ? "text-slate-500" : "text-slate-500"}>&bull;</span>
        <span className={comment.post_status === "open" ? (isDark ? "text-emerald-300" : "text-emerald-700") : (isDark ? "text-slate-400" : "text-slate-500")}>
          {comment.post_status}
        </span>
      </div>
      <Link href={`/public/forum/${comment.post_id}` as Route} className="mt-3 block text-lg font-semibold hover:underline">
        {comment.post_headline}
      </Link>
      {comment.post_title ? <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{comment.post_title}</p> : null}
      <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{comment.body}</p>
      <div className={`mt-4 flex flex-wrap gap-3 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>
        <span>{comment.like_count} likes</span>
        <span>{comment.dislike_count} dislikes</span>
      </div>
    </article>
  )
}

function EmptyState({ isDark, text }: { isDark: boolean, text: string }) {
  return (
    <div className={`rounded-3xl border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-[#d8c6ab] text-slate-500"}`}>
      {text}
    </div>
  )
}
