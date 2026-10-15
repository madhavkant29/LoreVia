"use client"

import Link from "next/link"
import type { Route } from "next"
import React, { useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore, formatWordProgress } from "@/lib/utils/publicForum"
import type { PublicBook } from "@/types/book"
import type { PublicUserActivityComment, PublicUserActivityPost, PublicUserProfile } from "@/types/public"

function buildEmptyPublicProfile(username: string): PublicUserProfile {
  return {
    user_id: "",
    username,
    reputation_score: 0,
    reputation_likes_received: 0,
    reputation_dislikes_received: 0,
    trust_level: "New",
    forum_post_count: 0,
    forum_comment_count: 0,
    current_project: null,
    public_books_count: 0,
    public_books: [],
    public_analytics: {
      total_book_views: 0,
      total_unique_readers_30d: 0,
      total_chapter_views: 0,
      total_public_books: 0,
      total_chapters: 0,
      total_words: 0,
      latest_published_at: null,
      open_forum_discussions_count: 0,
    },
    posts: [],
    comments: [],
    created_at: "",
  }
}

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
  const fallbackProfile = buildEmptyPublicProfile(username)
  const { data: profile = initialProfile, isLoading: loading, isError } = useQuery<PublicUserProfile | null>({
    queryKey: asQueryKey(`public:writer:${username}`),
    queryFn: () => publicApi.getUserProfile(username),
    enabled: Boolean(username),
    staleTime: 0,
    refetchOnMount: "always",
    ...(initialProfile !== undefined ? { initialData: initialProfile } : {}),
  })
  const resolvedProfile = profile ?? (username ? fallbackProfile : null)

  if (loading) {
    return <div className={`mx-auto max-w-5xl px-4 py-20 text-center text-sm ${isDark ? "text-slate-500" : "text-slate-400"}`}>Loading writer profile...</div>
  }

  if (!resolvedProfile && !isError) {
    return <div className={`mx-auto max-w-5xl px-4 py-20 text-center text-sm ${isDark ? "text-slate-500" : "text-slate-400"}`}>Writer profile not found.</div>
  }

  const profileView = resolvedProfile as PublicUserProfile
  const project = profileView.current_project
  const publicSampleHref = project?.public_book_id ? `/public/${project.public_book_id}` : null
  const forumDiscussionHref = project?.forum_post_id ? `/public/forum/${project.forum_post_id}` : null

  const pageClass = isDark ? "bg-[#10161d] text-slate-100" : "bg-[#f3f4f6] text-slate-950"
  const insetClass = isDark ? "border-white/[0.08] bg-[#111820]" : "border-[#e5e7eb] bg-[#fbfcfd]"
  const mutedText = isDark ? "text-slate-400" : "text-slate-600"
  const softText = isDark ? "text-slate-500" : "text-slate-500"
  const eyebrowClass = isDark ? "text-[#e0bc67]" : "text-[#b66b19]"
  const accentButtonClass = isDark ? "bg-white text-slate-950 hover:bg-slate-200" : "bg-slate-950 text-white hover:bg-slate-800"
  const secondaryButtonClass = isDark
    ? "border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.08]"
    : "border-slate-200 bg-white text-slate-900 hover:bg-slate-50"

  const overviewStats = [
    {
      label: "Reputation",
      value: formatReputationScore(profileView.reputation_score),
      detail: profileView.trust_level,
      icon: <SparkIcon />,
    },
    {
      label: "Public books",
      value: String(profileView.public_books_count),
      detail: "Published in the library",
      icon: <BookIcon />,
    },
    {
      label: "Readers, 30 days",
      value: profileView.public_analytics.total_unique_readers_30d.toLocaleString(),
      detail: "Across public books",
      icon: <ReadersIcon />,
    },
    {
      label: "Forum contributions",
      value: String(profileView.forum_post_count + profileView.forum_comment_count),
      detail: `${profileView.forum_post_count} posts · ${profileView.forum_comment_count} comments`,
      icon: <PostIcon />,
    },
  ]

  return (
    <div className={`min-h-screen ${pageClass}`}>
      <div className="mx-auto max-w-[1240px] px-4 py-8 sm:px-6 lg:px-8">
        <Link href="/public" className={`inline-flex items-center gap-2 text-sm transition ${softText} ${isDark ? "hover:text-white" : "hover:text-slate-900"}`}>
          <ArrowLeftIcon />
          Back to public library
        </Link>

        <section data-testid="writer-profile-masthead" className={`mt-5 border-y py-6 lg:py-8 ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"}`}>
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
              <div className={`flex h-20 w-20 shrink-0 items-center justify-center rounded-full border text-3xl ${insetClass} ${isDark ? "text-slate-200" : "text-slate-700"}`}>
                @
              </div>

              <div className="max-w-xl">
                <p className={`text-sm font-semibold ${eyebrowClass}`}>Public writer profile</p>
                <h1 className="mt-2 font-display text-[2.3rem] tracking-[-0.035em] sm:text-[2.7rem]">@{profileView.username}</h1>
                <p className={`mt-3 max-w-lg text-sm leading-7 ${mutedText}`}>
                  Visible public profile for reading activity, discussion history, and the public books this writer has chosen to share.
                </p>
                <p className={`mt-4 text-xs font-semibold ${softText}`}>Public forum status: public</p>
              </div>
            </div>

            <Link
              href={`/chats?username=${encodeURIComponent(profileView.username)}` as Route}
              className={`inline-flex h-10 items-center justify-center rounded-md border px-4 text-sm font-semibold transition ${secondaryButtonClass}`}
            >
              Message @{profileView.username}
            </Link>
          </div>

          <div className="mt-6 grid gap-5 border-t pt-6 sm:grid-cols-2 xl:grid-cols-4">
            {overviewStats.map((stat) => (
              <CompactStat
                key={stat.label}
                isDark={isDark}
                label={stat.label}
                value={stat.value}
                detail={stat.detail}
                icon={stat.icon}
              />
            ))}
          </div>
          <p className={`mt-6 border-t pt-4 text-xs ${softText}`}>
            {profileView.public_analytics.total_book_views.toLocaleString()} total book views
            {" · "}{profileView.public_analytics.total_chapters.toLocaleString()} visible chapters
            {" · "}{formatWordProgress(profileView.public_analytics.total_words)} visible
          </p>
        </section>

        <SectionCard
          isDark={isDark}
          eyebrow="Public books"
          title="Published books"
          trailing={<p className={`text-sm ${softText}`}>{profileView.public_books_count} visible upload{profileView.public_books_count === 1 ? "" : "s"}</p>}
          className="mt-10"
        >
          <div className="mt-5">
            {profileView.public_books.length > 0 ? (
              <div className={`border-y ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"}`}>
                {profileView.public_books.map((book) => (
                  <PublicBookCard key={book.id} isDark={isDark} book={book} />
                ))}
              </div>
            ) : (
              <InlineEmptyState isDark={isDark} icon={<BookIcon />} text="This writer has not surfaced any visible creator-published public books yet." />
            )}
          </div>
        </SectionCard>

        <SectionCard
          isDark={isDark}
          eyebrow="Activity"
          title="Discussion history"
          trailing={
            <div className={`inline-flex rounded-md p-1 ${isDark ? "bg-white/[0.05]" : "bg-[#f0f2f5]"}`}>
              <TabButton isDark={isDark} active={activeTab === "posts"} onClick={() => setActiveTab("posts")} label={`Posts (${profileView.posts.length})`} />
              <TabButton isDark={isDark} active={activeTab === "comments"} onClick={() => setActiveTab("comments")} label={`Comments (${profileView.comments.length})`} />
            </div>
          }
          className="mt-10"
        >
          <div className="mt-5">
            {activeTab === "posts" ? (
              <div className={`border-y ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"}`}>
                {profileView.posts.length === 0 ? (
                  <InlineEmptyState isDark={isDark} icon={<BubbleIcon />} text="No public posts are visible for this writer yet." />
                ) : profileView.posts.map((post) => (
                  <PostActivityCard key={post.id} isDark={isDark} post={post} />
                ))}
              </div>
            ) : (
              <div className={`border-y ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"}`}>
                {profileView.comments.length === 0 ? (
                  <InlineEmptyState isDark={isDark} icon={<BubbleIcon />} text="No public comments are visible for this writer yet." />
                ) : profileView.comments.map((comment) => (
                  <CommentActivityCard key={comment.id} isDark={isDark} comment={comment} />
                ))}
              </div>
            )}
          </div>
        </SectionCard>

        <SectionCard
          isDark={isDark}
          eyebrow="Surfaced project"
          title={project?.title || "No public sample surfaced yet"}
          className="mt-10"
        >
          <div className="mt-5">
            {project ? (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_16rem]">
                <div className="py-2">
                  <div className={`flex flex-wrap items-center gap-2 text-xs font-semibold ${softText}`}>
                    {project.genre ? <span>{project.genre}</span> : null}
                    {project.genre ? <span aria-hidden="true">&bull;</span> : null}
                    <span>{formatWordProgress(project.progress_words)}</span>
                  </div>
                  <p className={`mt-4 text-sm leading-7 ${mutedText}`}>{project.description || "This writer has not added a project description yet."}</p>
                  {forumDiscussionHref || publicSampleHref ? (
                    <div className="mt-5 flex flex-wrap gap-3">
                      {forumDiscussionHref ? (
                        <Link href={forumDiscussionHref as Route} className={`inline-flex rounded-md px-4 py-2 text-sm font-semibold transition ${accentButtonClass}`}>
                          Open forum discussion
                        </Link>
                      ) : null}
                      {publicSampleHref ? (
                        <Link href={publicSampleHref as Route} className={`inline-flex rounded-md border px-4 py-2 text-sm font-semibold transition ${secondaryButtonClass}`}>
                          Read public sample
                        </Link>
                      ) : null}
                    </div>
                  ) : null}
                </div>

                <div className={`border-l pl-6 ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"}`}>
                  <p className={`text-sm font-semibold ${softText}`}>Public reach</p>
                  <p className="mt-3 text-[1.75rem] font-semibold tracking-[-0.02em]">{profileView.public_analytics.total_chapter_views.toLocaleString()}</p>
                  <p className={`mt-3 text-sm leading-7 ${mutedText}`}>Chapter opens across this writer&apos;s visible public uploads.</p>
                </div>
              </div>
            ) : (
              <InlineEmptyState isDark={isDark} icon={<PageIcon />} text="This member has not surfaced a sample or manuscript in the public layer yet." />
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  )
}

function SectionCard({
  isDark,
  eyebrow,
  title,
  trailing,
  className = "",
  children,
}: {
  isDark: boolean
  eyebrow: string
  title: string
  trailing?: React.ReactNode
  className?: string
  children: React.ReactNode
}) {
  return (
    <section className={`border-t pt-8 ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"} ${className}`.trim()}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`text-sm font-semibold ${isDark ? "text-slate-400" : "text-slate-600"}`}>{eyebrow}</p>
          <h2 className="mt-1 font-display text-[2rem] tracking-[-0.03em]">{title}</h2>
        </div>
        {trailing ? <div className="sm:pt-1">{trailing}</div> : null}
      </div>
      {children}
    </section>
  )
}

function CompactStat({
  isDark,
  label,
  value,
  detail,
  icon,
}: {
  isDark: boolean
  label: string
  value: string
  detail: string
  icon: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-3">
      <div className={`mt-0.5 ${isDark ? "text-slate-400" : "text-slate-500"}`}>{icon}</div>
      <div>
        <p className="text-lg font-semibold tracking-[-0.02em]">{value}</p>
        <p className={`mt-1 text-xs uppercase tracking-[0.14em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>{label}</p>
        <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{detail}</p>
      </div>
    </div>
  )
}

function TabButton({ isDark, active, onClick, label }: { isDark: boolean; active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-sm px-4 py-2 text-sm font-semibold transition ${
        active
          ? isDark
            ? "bg-[#f0b323] text-slate-950"
            : "bg-slate-950 text-white"
          : isDark
            ? "text-slate-300 hover:bg-white/10"
            : "text-slate-700 hover:bg-white"
      }`}
    >
      {label}
    </button>
  )
}

function PublicBookCard({ isDark, book }: { isDark: boolean; book: PublicBook }) {
  return (
    <article className={`border-b py-6 last:border-b-0 ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]">
        <span className={isDark ? "text-cyan-300" : "text-cyan-700"}>{book.genre || "Unspecified genre"}</span>
        <span className="text-slate-400">&bull;</span>
        <span className={isDark ? "text-slate-500" : "text-slate-500"}>{formatCompactDate(book.published_at)}</span>
      </div>
      <Link href={`/public/${book.public_slug || book.id}` as Route} className="mt-3 block font-display text-[1.8rem] tracking-[-0.03em] hover:underline">
        {book.title}
      </Link>
      {book.description ? <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{book.description}</p> : null}
      <div className={`mt-4 flex flex-wrap gap-3 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>
        <span>{book.total_chapters ?? 0} chapters</span>
        <span>{book.analytics?.book_view_count?.toLocaleString?.() ?? 0} views</span>
      </div>
      <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm font-semibold">
        <Link href={`/public/${book.public_slug || book.id}` as Route} className={isDark ? "text-teal-300 hover:text-teal-200" : "text-[#1f615d] hover:text-[#174c49]"}>
          Read public book &rarr;
        </Link>
        {book.active_forum_post_id ? (
          <Link href={`/public/forum/${book.active_forum_post_id}` as Route} className={isDark ? "text-slate-300 hover:text-white" : "text-slate-700 hover:text-slate-950"}>
            Open discussion &rarr;
          </Link>
        ) : null}
      </div>
    </article>
  )
}

function PostActivityCard({ isDark, post }: { isDark: boolean; post: PublicUserActivityPost }) {
  const href = `/public/forum/${post.id}` as Route
  const typeLabel = post.thread_type === "general" ? "General" : "Novel"
  const statusLabel = post.status === "open" ? "Open" : "Closed"

  return (
    <article className={`border-b py-6 last:border-b-0 ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]">
        <span className={isDark ? "text-cyan-300" : "text-cyan-700"}>{typeLabel}</span>
        <span className="text-slate-400">&bull;</span>
        <span className={post.status === "open" ? (isDark ? "text-emerald-300" : "text-emerald-700") : (isDark ? "text-slate-400" : "text-slate-500")}>{statusLabel}</span>
      </div>
      <Link href={href} className="mt-3 block font-display text-[1.55rem] tracking-[-0.03em] hover:underline">{post.headline}</Link>
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

function CommentActivityCard({ isDark, comment }: { isDark: boolean; comment: PublicUserActivityComment }) {
  return (
    <article className={`border-b py-6 last:border-b-0 ${isDark ? "border-white/[0.08]" : "border-[#dde2e8]"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]">
        <span className={comment.thread_type === "general" ? (isDark ? "text-cyan-300" : "text-cyan-700") : (isDark ? "text-amber-300" : "text-amber-700")}>
          {comment.thread_type === "general" ? "General" : "Novel"}
        </span>
        <span className="text-slate-400">&bull;</span>
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

function InlineEmptyState({ isDark, icon, text }: { isDark: boolean; icon: React.ReactNode; text: string }) {
  return (
    <div className={`flex items-center gap-3 py-5 text-sm ${isDark ? "text-slate-500" : "text-slate-500"}`}>
      <span className={isDark ? "text-slate-400" : "text-slate-500"}>{icon}</span>
      <span>{text}</span>
    </div>
  )
}

function ArrowLeftIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 18l-6-6 6-6" />
    </svg>
  )
}

function SparkIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" />
    </svg>
  )
}

function PostIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <rect x="5" y="4" width="14" height="16" rx="2.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 9h8M8 13h8" />
    </svg>
  )
}

function ReadersIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.5 11a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM15.5 10a2 2 0 100-4 2 2 0 000 4zM4.5 18a4 4 0 018 0M13 18a3.5 3.5 0 017 0" />
    </svg>
  )
}

function BookIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 5.5h11.5A1.5 1.5 0 0119 7v11.5H7.5A2.5 2.5 0 015 16V7A1.5 1.5 0 016.5 5.5z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 18.5V8A2.5 2.5 0 015 10.5V16a2.5 2.5 0 002.5 2.5z" />
    </svg>
  )
}

function PageIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 4.5h8l3 3V19.5H7z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 4.5v4h4" />
    </svg>
  )
}

function BubbleIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 7.5h12A2.5 2.5 0 0120.5 10v4A2.5 2.5 0 0118 16.5h-7L6 20v-3.5A2.5 2.5 0 013.5 14v-4A2.5 2.5 0 016 7.5z" />
    </svg>
  )
}
