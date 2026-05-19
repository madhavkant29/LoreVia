"use client"

import Link from "next/link"
import type { Route } from "next"
import { useEffect, useState } from "react"

import { authApi } from "@/lib/api/auth"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { publicApi } from "@/lib/api/public"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore } from "@/lib/utils/publicForum"
import type { PublicForumComment, PublicForumInterest, PublicForumPost } from "@/types/public"
import type { User } from "@/types/user"

export function PublicForumPostPageClient({
  postId,
  initialPost,
}: {
  postId: string
  initialPost: PublicForumPost
}) {
  const [post, setPost] = useState<PublicForumPost | null>(initialPost)
  const [comments, setComments] = useState<PublicForumComment[]>([])
  const [interests, setInterests] = useState<PublicForumInterest[]>([])
  const [viewer, setViewer] = useState<User | null>(null)
  const [draft, setDraft] = useState("")
  const [interestDraft, setInterestDraft] = useState("")
  const [editHeadline, setEditHeadline] = useState(initialPost.headline)
  const [editBody, setEditBody] = useState(initialPost.body)
  const [editDesiredCount, setEditDesiredCount] = useState(initialPost.desired_beta_reader_count ? String(initialPost.desired_beta_reader_count) : "")
  const [editAllowContactRequests, setEditAllowContactRequests] = useState(initialPost.allow_contact_requests)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [interestSubmitting, setInterestSubmitting] = useState(false)
  const [interestLoadFailed, setInterestLoadFailed] = useState(false)
  const [editing, setEditing] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)
  const [reactingId, setReactingId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const resetEditorFromPost = (source: PublicForumPost) => {
    setEditHeadline(source.headline)
    setEditBody(source.body)
    setEditDesiredCount(source.desired_beta_reader_count ? String(source.desired_beta_reader_count) : "")
    setEditAllowContactRequests(source.allow_contact_requests)
  }

  useEffect(() => {
    let active = true

    const load = async () => {
      setLoading(true)
      setStatus(null)
      try {
        const [postPayload, commentsPayload, viewerPayload] = await Promise.all([
          publicApi.getForumPost(postId),
          publicApi.listForumComments(postId),
          authApi.me().catch(() => null),
        ])
        if (!active) return
        setPost(postPayload)
        setComments(commentsPayload)
        setViewer(viewerPayload)
        resetEditorFromPost(postPayload)
        setInterestLoadFailed(false)

        if (viewerPayload?.id === postPayload.author_user_id) {
          try {
            const interestPayload = await publicApi.listForumInterests(postId)
            if (!active) return
            setInterests(interestPayload)
          } catch {
            if (!active) return
            setInterests([])
            setInterestLoadFailed(true)
          }
        } else {
          setInterests([])
        }
      } catch {
        if (!active) return
        setStatus("Could not load this surfaced discussion.")
      } finally {
        if (!active) return
        setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [postId])

  const isAuthorViewer = viewer?.id === post?.author_user_id
  const isPubliclyInteractive = post?.status === "open"
  const canManagePublicAuthoring = canUseAuthorFeatures(viewer?.tier)
  const isNovelThread = (post?.thread_type || "novel") === "novel"

  const refreshComments = async () => {
    const items = await publicApi.listForumComments(postId)
    setComments(items)
    setPost((current) => current ? { ...current, comment_count: items.length } : current)
  }

  const submitComment = async () => {
    if (!viewer) {
      setStatus("Sign in to leave a public comment on this surfaced discussion.")
      return
    }
    if (!draft.trim()) return
    setSubmitting(true)
    setStatus(null)
    try {
      const created = await publicApi.createForumComment(postId, draft.trim())
      setComments((current) => [...current, created])
      setPost((current) => current ? { ...current, comment_count: current.comment_count + 1 } : current)
      setDraft("")
    } catch {
      setStatus("Could not post your comment.")
    } finally {
      setSubmitting(false)
    }
  }

  const submitInterest = async () => {
    if (!post || !viewer) {
      setStatus("Sign in to contact this author.")
      return
    }
    if (!interestDraft.trim()) return
    setInterestSubmitting(true)
    setStatus(null)
    try {
      const created = await publicApi.createForumInterest(post.id, interestDraft.trim())
      setInterestDraft("")
      setPost((current) => current ? {
        ...current,
        interest_count: current.interest_count + 1,
        viewer_interest_status: created.status,
      } : current)
      setStatus("Your collaborator interest note was sent to the author.")
    } catch {
      setStatus("Could not send your collaborator note.")
    } finally {
      setInterestSubmitting(false)
    }
  }

  const saveEdit = async () => {
    if (!post) return
    if (!editHeadline.trim() || !editBody.trim()) {
      setStatus("Headline and discussion details are required.")
      return
    }
    const hasDesiredCount = editDesiredCount.trim().length > 0
    const parsedDesiredCount = hasDesiredCount ? Number.parseInt(editDesiredCount, 10) : null
    if (isNovelThread && hasDesiredCount && (!Number.isFinite(parsedDesiredCount) || (parsedDesiredCount ?? 0) < 1)) {
      setStatus("Desired beta readers must be a whole number greater than zero.")
      return
    }
    setSavingEdit(true)
    setStatus(null)
    try {
      const updated = await publicApi.updateForumPost(post.id, {
        threadType: post.thread_type === "general" ? "general" : "novel",
        headline: editHeadline.trim(),
        body: editBody.trim(),
        desiredBetaReaderCount: isNovelThread ? parsedDesiredCount : null,
        allowContactRequests: isNovelThread ? editAllowContactRequests : false,
        status: post.status,
      })
      setPost(updated)
      setEditing(false)
      resetEditorFromPost(updated)
      setStatus("Your public discussion was updated.")
    } catch {
      setStatus("Could not update this discussion.")
    } finally {
      setSavingEdit(false)
    }
  }

  const saveDiscussionStatus = async (nextStatus: string) => {
    if (!post) return
    setSavingEdit(true)
    setStatus(null)
    try {
      const updated = await publicApi.updateForumPost(post.id, {
        threadType: post.thread_type === "general" ? "general" : "novel",
        headline: post.headline,
        body: post.body,
        desiredBetaReaderCount: isNovelThread ? post.desired_beta_reader_count : null,
        allowContactRequests: isNovelThread ? post.allow_contact_requests : false,
        status: nextStatus,
      })
      setPost(updated)
      setEditing(false)
      resetEditorFromPost(updated)
      setStatus(
        nextStatus === "closed"
          ? "Your public discussion is now closed."
          : "Your public discussion is live again.",
      )
    } catch {
      setStatus(
        nextStatus === "closed"
          ? "Could not close this discussion."
          : "Could not reopen this discussion.",
      )
    } finally {
      setSavingEdit(false)
    }
  }

  const react = async (comment: PublicForumComment, reaction: "like" | "dislike") => {
    if (!viewer) {
      setStatus("Sign in to react to comments.")
      return
    }
    setReactingId(comment.id)
    setStatus(null)
    try {
      const nextReaction = comment.reaction === reaction ? "clear" : reaction
      const updated = await publicApi.reactToForumComment(comment.id, nextReaction)
      setComments((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch {
      setStatus("Could not update that reaction.")
      await refreshComments().catch(() => undefined)
    } finally {
      setReactingId(null)
    }
  }

  if (loading) {
    return <div className={`mx-auto max-w-4xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>Loading discussion...</div>
  }

  if (!post) {
    return <div className={`mx-auto max-w-4xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>{status || "Discussion not found."}</div>
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#0a0f14] text-slate-100" : "bg-[#edf1f5] text-slate-950"}`}>
      <div className={`border-b backdrop-blur ${isDark ? "border-white/10 bg-[#0f141b]/95" : "border-slate-200 bg-white/95"}`}>
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Link href="/public/forum" className={`${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>Forum</Link>
            <MetaDivider isDark={isDark} />
            {post.author_username ? (
              <Link href={`/public/writers/${post.author_username}` as Route} className={`${isDark ? "text-slate-400 hover:text-amber-300" : "text-slate-500 hover:text-orange-700"}`}>
                @{post.author_username}
              </Link>
            ) : null}
            {post.title ? (
              <>
                <MetaDivider isDark={isDark} />
                <span className={isDark ? "text-slate-300" : "text-slate-700"}>{post.title}</span>
              </>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_312px] lg:px-8">
        <main className="min-w-0">
          <article className={`overflow-hidden rounded-3xl border shadow-[0_18px_40px_rgba(15,23,42,0.08)] ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
            <div className="flex">
              <div className={`hidden w-[72px] shrink-0 flex-col items-center justify-start gap-2 border-r px-3 py-4 md:flex ${isDark ? "border-white/10 bg-[#0f141b]" : "border-slate-200 bg-slate-50/70"}`}>
                <VoteArrowIcon className={isDark ? "text-slate-500" : "text-slate-400"} />
                <span className="text-xl font-semibold">{Math.round(post.discoverability_score)}</span>
                <span className={`text-[11px] uppercase tracking-[0.16em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>pulse</span>
              </div>

              <div className="min-w-0 flex-1 px-4 py-5 sm:px-5">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <UserBadge isDark={isDark} username={post.author_username || post.author || "writer"} />
                  <MetaText isDark={isDark}>{formatRelativeDay(post.created_at)}</MetaText>
                  <MetaDivider isDark={isDark} />
                  <MetaText isDark={isDark}>{post.author_trust_level}</MetaText>
                  <MetaDivider isDark={isDark} />
                  <MetaText isDark={isDark}>rep {formatReputationScore(post.author_reputation_score)}</MetaText>
                  <span className={`rounded-full px-2 py-1 font-semibold ${isPubliclyInteractive ? (isDark ? "bg-emerald-400/12 text-emerald-200" : "bg-emerald-100 text-emerald-700") : (isDark ? "bg-white/[0.06] text-slate-400" : "bg-slate-100 text-slate-600")}`}>
                    {isPubliclyInteractive ? "thread open" : "thread closed"}
                  </span>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                  <span className={isDark ? "text-amber-300" : "text-orange-700"}>{isNovelThread ? "novel discussion" : "general discussion"}</span>
                  {isNovelThread ? (
                    <>
                      <MetaDivider isDark={isDark} />
                      <span className={isDark ? "text-slate-500" : "text-slate-500"}>target {post.desired_beta_reader_count ?? "open-ended"} readers</span>
                    </>
                  ) : null}
                </div>

                <h1 className="mt-3 text-2xl font-semibold tracking-tight sm:text-[2rem]">{post.headline}</h1>
                {post.title ? <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.title}</p> : null}
                <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{post.body}</p>

                <div className="mt-5 flex flex-wrap items-center gap-2 text-xs">
                  <ActionPill isDark={isDark} icon={<CommentBubbleIcon className="h-3.5 w-3.5" />}>
                    {post.comment_count} comments
                  </ActionPill>
                  {isNovelThread ? (
                    <ActionPill isDark={isDark} icon={<InboxIcon className="h-3.5 w-3.5" />}>
                      {post.interest_count} reader notes
                    </ActionPill>
                  ) : null}
                  {isNovelThread ? (
                    <ActionPill isDark={isDark}>
                      {post.rating_summary.average_rating?.toFixed(1) ?? "n/a"} avg from {post.rating_summary.rating_count}
                    </ActionPill>
                  ) : null}
                </div>

                {isAuthorViewer ? (
                  <div className="mt-5 flex flex-wrap gap-3">
                    {canManagePublicAuthoring || !isNovelThread ? (
                      <button
                        type="button"
                        onClick={() => {
                          setEditing((current) => !current)
                          setStatus(null)
                        }}
                        className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
                      >
                        {editing ? "Close editor" : "Edit discussion"}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={savingEdit || (isNovelThread && !canManagePublicAuthoring && !isPubliclyInteractive)}
                      onClick={() => void saveDiscussionStatus(isPubliclyInteractive ? "closed" : "open")}
                      className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09] disabled:bg-slate-300"}`}
                    >
                      {savingEdit ? "Saving..." : isPubliclyInteractive ? "Close discussion" : isNovelThread ? (canManagePublicAuthoring ? "Reopen discussion" : "Closed on free plan") : "Reopen discussion"}
                    </button>
                  </div>
                ) : null}

                {isAuthorViewer && isNovelThread && !canManagePublicAuthoring ? (
                  <div className={`mt-4 rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
                    Public discussions require an Author or Architect plan. You can still close this discussion, but editing or reopening it needs a paid author plan.
                  </div>
                ) : null}

                {!isPubliclyInteractive ? (
                  <div className={`mt-4 rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
                    This discussion is closed. It stays visible for reference, but new comments, reactions, and collaborator requests are paused until the author reopens it.
                  </div>
                ) : null}
              </div>
            </div>
          </article>

          {isAuthorViewer && (canManagePublicAuthoring || !isNovelThread) && editing ? (
            <section className={`mt-5 rounded-3xl border p-5 ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Author controls</p>
              <h2 className="mt-2 text-xl font-semibold">Refine this thread</h2>
              <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                {isNovelThread ? "Tighten the ask, clarify the kind of beta feedback you need, and keep the public thread clean while the manuscript stays private." : "Refine the discussion prompt so other writers can jump into the conversation quickly."}
              </p>
              <div className="mt-4 space-y-3">
                <input
                  value={editHeadline}
                  onChange={(event) => setEditHeadline(event.target.value)}
                  placeholder="Headline"
                  className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                />
                <textarea
                  value={editBody}
                  onChange={(event) => setEditBody(event.target.value)}
                  placeholder="What kind of beta feedback are you looking for?"
                  className={`min-h-[10rem] w-full rounded-2xl border px-4 py-3 text-sm leading-6 outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                />
                {isNovelThread ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      value={editDesiredCount}
                      onChange={(event) => setEditDesiredCount(event.target.value)}
                      placeholder="Desired beta readers"
                      inputMode="numeric"
                      className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                    />
                    <label className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100" : "border-slate-200 bg-slate-50 text-slate-900"}`}>
                      <span>Allow collaborator contact requests</span>
                      <input
                        type="checkbox"
                        checked={editAllowContactRequests}
                        onChange={(event) => setEditAllowContactRequests(event.target.checked)}
                        className="h-4 w-4"
                      />
                    </label>
                  </div>
                ) : null}
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => void saveEdit()}
                    disabled={savingEdit}
                    className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09] disabled:bg-slate-300"}`}
                  >
                    {savingEdit ? "Saving..." : "Save discussion"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false)
                      resetEditorFromPost(post)
                    }}
                    className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </section>
          ) : null}

          <section className={`mt-5 rounded-3xl border ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
            <div className={`border-b px-4 py-4 sm:px-5 ${isDark ? "border-white/10" : "border-slate-200"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Conversation</p>
                  <h2 className="mt-2 text-xl font-semibold">Public comments</h2>
                </div>
                <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{viewer ? `Signed in as @${viewer.username || "member"}` : "Sign in to join the discussion."}</p>
              </div>

              {status ? <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{status}</p> : null}

              {isPubliclyInteractive ? (
                <div className="mt-4 rounded-2xl border p-3 md:p-4">
                  <div className={`rounded-2xl ${isDark ? "border-white/10 bg-[#0f141b]" : "bg-slate-50"}`}>
                    <textarea
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      placeholder="Add a thoughtful public comment about pacing, clarity, emotional payoff, or what you'd want to review."
                      className={`min-h-[8.5rem] w-full rounded-2xl border px-4 py-3 text-sm leading-6 outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                    />
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      disabled={submitting || !draft.trim()}
                      onClick={() => void submitComment()}
                      className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09] disabled:bg-slate-300"}`}
                    >
                      {submitting ? "Posting..." : "Post comment"}
                    </button>
                    <MetaText isDark={isDark}>Best comments mention what worked, what felt unclear, and what the author should revisit next.</MetaText>
                  </div>
                </div>
              ) : (
                <div className={`mt-4 rounded-2xl border border-dashed px-4 py-4 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-slate-200 text-slate-500"}`}>
                  Public comments are paused while this discussion is closed.
                </div>
              )}
            </div>

            <div className="divide-y divide-slate-200/80 dark:divide-white/10">
              {comments.length === 0 ? (
                <div className={`px-4 py-5 text-sm sm:px-5 ${isDark ? "text-slate-500" : "text-slate-500"}`}>No public comments are visible on this discussion yet.</div>
              ) : comments.map((comment) => (
                <CommentRow
                  key={comment.id}
                  comment={comment}
                  isDark={isDark}
                  isPubliclyInteractive={isPubliclyInteractive}
                  reactingId={reactingId}
                  onReact={react}
                />
              ))}
            </div>
          </section>
        </main>

        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <section className={`rounded-3xl border p-4 shadow-sm ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Thread snapshot</p>
            <div className="mt-4 grid gap-3 text-sm">
              <div className={`rounded-2xl px-4 py-4 ${isDark ? "bg-[#0f141b]" : "bg-slate-50"}`}>
                <p className={`text-[11px] uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Author</p>
                <p className="mt-2 text-base font-semibold">@{post.author_username || post.author || "writer"}</p>
                <p className={`mt-1 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.author_trust_level} / rep {formatReputationScore(post.author_reputation_score)}</p>
              </div>
              <div className={`rounded-2xl px-4 py-4 ${isDark ? "bg-[#0f141b]" : "bg-slate-50"}`}>
                <p className={`text-[11px] uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Signals</p>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <MiniMetric isDark={isDark} value={String(post.comment_count)} label="comments" />
                  <MiniMetric isDark={isDark} value={String(isNovelThread ? post.interest_count : 0)} label={isNovelThread ? "reader notes" : "replies"} />
                  <MiniMetric isDark={isDark} value={isNovelThread ? (post.rating_summary.average_rating?.toFixed(1) ?? "n/a") : "n/a"} label={isNovelThread ? "avg rating" : "ratings"} />
                  <MiniMetric isDark={isDark} value={isNovelThread ? String(post.desired_beta_reader_count ?? "?") : "open"} label={isNovelThread ? "reader target" : "scope"} />
                </div>
              </div>
            </div>
          </section>

          {!isAuthorViewer && isNovelThread ? (
            <section className={`rounded-3xl border p-4 shadow-sm ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Collaborator contact</p>
              <h2 className="mt-2 text-lg font-semibold">Offer to beta read</h2>
              <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                This thread is meant to gather serious reader intent around a private manuscript, not to expose the manuscript itself.
              </p>

              {post.viewer_interest_status ? (
                <div className={`mt-4 rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
                  You already sent this author a collaborator note. Current status: {post.viewer_interest_status}.
                </div>
              ) : post.allow_contact_requests && isPubliclyInteractive ? (
                <div className="mt-4">
                  {post.author_username ? (
                    <Link
                      href={`/chats?username=${encodeURIComponent(post.author_username)}` as Route}
                      className={`mb-3 inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "border border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
                    >
                      Open direct chat
                    </Link>
                  ) : null}
                  <textarea
                    value={interestDraft}
                    onChange={(event) => setInterestDraft(event.target.value)}
                    placeholder="Tell the author what genres you read well, what feedback you can provide, and why you'd be a useful beta reader."
                    className={`min-h-[8rem] w-full rounded-2xl border px-4 py-3 text-sm leading-6 outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      disabled={interestSubmitting || !interestDraft.trim()}
                      onClick={() => void submitInterest()}
                      className={`inline-flex h-10 w-full items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09] disabled:bg-slate-300"}`}
                    >
                      {interestSubmitting ? "Sending..." : "Send collaborator note"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className={`mt-4 rounded-2xl border border-dashed px-4 py-4 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-slate-200 text-slate-500"}`}>
                  {isPubliclyInteractive
                    ? "This author is not taking direct collaborator requests through the public forum right now."
                    : "This discussion is closed, so direct collaborator requests are paused right now."}
                </div>
              )}
            </section>
          ) : isAuthorViewer && isNovelThread ? (
            <section className={`rounded-3xl border p-4 shadow-sm ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Incoming collaborators</p>
                  <h2 className="mt-2 text-lg font-semibold">Reader interest</h2>
                </div>
                <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{interests.length} request{interests.length === 1 ? "" : "s"}</p>
              </div>

              {interestLoadFailed ? (
                <div className={`mt-4 rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
                  Collaborator notes could not be loaded right now. Refresh this page to try again.
                </div>
              ) : interests.length === 0 ? (
                <div className={`mt-4 rounded-2xl border border-dashed px-4 py-4 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-slate-200 text-slate-500"}`}>
                  No collaborator notes have arrived for this public discussion yet.
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  {interests.map((interest) => (
                    <article key={interest.id} className={`rounded-2xl border px-4 py-4 ${isDark ? "border-white/10 bg-[#0f141b]" : "border-slate-200 bg-slate-50"}`}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold">@{interest.interested_username || interest.interested_email}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>{interest.interested_email}</p>
                        </div>
                        <div className="text-right">
                          <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-amber-300" : "text-orange-700"}`}>{interest.status}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{new Date(interest.created_at).toLocaleString()}</p>
                        </div>
                      </div>
                      <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{interest.message}</p>
                    </article>
                  ))}
                </div>
              )}
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  )
}

function CommentRow({
  comment,
  isDark,
  isPubliclyInteractive,
  reactingId,
  onReact,
}: {
  comment: PublicForumComment
  isDark: boolean
  isPubliclyInteractive: boolean
  reactingId: string | null
  onReact: (comment: PublicForumComment, reaction: "like" | "dislike") => Promise<void>
}) {
  return (
    <article className="flex gap-3 px-4 py-4 sm:px-5">
      <div className={`mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${isDark ? "bg-[#202834] text-slate-100" : "bg-slate-100 text-slate-700"}`}>
        {(comment.author_username || "C").slice(0, 1).toUpperCase()}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {comment.author_username ? (
            <Link href={`/public/writers/${comment.author_username}` as Route} className={`font-semibold ${isDark ? "text-white hover:text-amber-300" : "text-slate-900 hover:text-orange-700"}`}>
              @{comment.author_username}
            </Link>
          ) : (
            <p className="font-semibold">Collaborator</p>
          )}
          <MetaText isDark={isDark}>{comment.author_trust_level}</MetaText>
          <MetaDivider isDark={isDark} />
          <MetaText isDark={isDark}>rep {formatReputationScore(comment.author_reputation_score)}</MetaText>
          {comment.can_edit ? (
            <>
              <MetaDivider isDark={isDark} />
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${isDark ? "bg-amber-400/15 text-amber-200" : "bg-orange-100 text-orange-700"}`}>You</span>
            </>
          ) : null}
          <MetaDivider isDark={isDark} />
          <MetaText isDark={isDark}>{new Date(comment.created_at).toLocaleString()}</MetaText>
        </div>

        <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{comment.body}</p>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <button
            type="button"
            disabled={!isPubliclyInteractive || reactingId === comment.id}
            onClick={() => void onReact(comment, "like")}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 font-semibold transition disabled:cursor-not-allowed disabled:opacity-80 ${comment.reaction === "like" ? (isDark ? "border-emerald-400/60 bg-emerald-400/15 text-emerald-200" : "border-emerald-300 bg-emerald-50 text-emerald-700") : (isDark ? "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300")}`}
          >
            <VoteArrowIcon className="h-4 w-4" />
            {comment.like_count}
          </button>
          <button
            type="button"
            disabled={!isPubliclyInteractive || reactingId === comment.id}
            onClick={() => void onReact(comment, "dislike")}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 font-semibold transition disabled:cursor-not-allowed disabled:opacity-80 ${comment.reaction === "dislike" ? (isDark ? "border-rose-400/60 bg-rose-400/15 text-rose-200" : "border-rose-300 bg-rose-50 text-rose-700") : (isDark ? "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300")}`}
          >
            <DownVoteIcon className="h-4 w-4" />
            {comment.dislike_count}
          </button>
          {!isPubliclyInteractive ? <MetaText isDark={isDark}>Reactions paused</MetaText> : null}
        </div>
      </div>
    </article>
  )
}

function formatRelativeDay(value: string): string {
  const timestamp = new Date(value).getTime()
  const deltaMinutes = Math.max(0, Math.floor((Date.now() - timestamp) / (1000 * 60)))
  if (deltaMinutes < 60) return `${Math.max(deltaMinutes, 1)}m ago`
  const deltaHours = Math.floor(deltaMinutes / 60)
  if (deltaHours < 24) return `${deltaHours}h ago`
  const deltaDays = Math.floor(deltaHours / 24)
  if (deltaDays === 1) return "1d ago"
  return `${deltaDays}d ago`
}

function MiniMetric({ isDark, value, label }: { isDark: boolean, value: string, label: string }) {
  return (
    <div>
      <p className="text-lg font-semibold">{value}</p>
      <p className={isDark ? "text-slate-500" : "text-slate-500"}>{label}</p>
    </div>
  )
}

function UserBadge({ isDark, username }: { isDark: boolean, username: string }) {
  return (
    <span className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 font-medium ${isDark ? "bg-white/[0.05] text-slate-100" : "bg-slate-100 text-slate-900"}`}>
      <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${isDark ? "bg-[#202834] text-slate-100" : "bg-white text-slate-700 ring-1 ring-slate-200"}`}>
        {username.slice(0, 1).toUpperCase()}
      </span>
      @{username}
    </span>
  )
}

function ActionPill({ children, icon, isDark }: { children: React.ReactNode, icon?: React.ReactNode, isDark: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 ${isDark ? "bg-white/[0.04] text-slate-300" : "bg-slate-100 text-slate-700"}`}>
      {icon}
      {children}
    </span>
  )
}

function MetaText({ children, isDark }: { children: React.ReactNode, isDark: boolean }) {
  return <span className={isDark ? "text-slate-500" : "text-slate-500"}>{children}</span>
}

function MetaDivider({ isDark }: { isDark: boolean }) {
  return <span className={`h-1 w-1 rounded-full ${isDark ? "bg-slate-600" : "bg-slate-400"}`} aria-hidden="true" />
}

function VoteArrowIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={`${className || "h-5 w-5"}`} aria-hidden="true">
      <path d="M10 3.5 16 10h-3.75v6.5h-4.5V10H4z" />
    </svg>
  )
}

function DownVoteIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={`${className || "h-5 w-5"} rotate-180`} aria-hidden="true">
      <path d="M10 3.5 16 10h-3.75v6.5h-4.5V10H4z" />
    </svg>
  )
}

function CommentBubbleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`${className || "h-4 w-4"}`} aria-hidden="true">
      <path d="M4 4.75h12a1.25 1.25 0 0 1 1.25 1.25v7A1.25 1.25 0 0 1 16 14.25H9.5l-3.75 2.5V14.25H4A1.25 1.25 0 0 1 2.75 13V6A1.25 1.25 0 0 1 4 4.75Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

function InboxIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`${className || "h-4 w-4"}`} aria-hidden="true">
      <path d="M4 6.5h12l1 6.5h-4.5L10 15.5 7.5 13H3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M4.5 6.5 6 4.5h8l1.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
