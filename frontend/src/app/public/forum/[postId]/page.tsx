"use client"

import Link from "next/link"
import type { Route } from "next"
import { useEffect, useState } from "react"
import { useParams } from "next/navigation"

import { authApi } from "@/lib/api/auth"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { publicApi } from "@/lib/api/public"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore } from "@/lib/utils/publicForum"
import type { PublicForumComment, PublicForumInterest, PublicForumPost } from "@/types/public"
import type { User } from "@/types/user"

export default function PublicForumPostPage() {
  const { postId } = useParams<{ postId: string }>()
  const [post, setPost] = useState<PublicForumPost | null>(null)
  const [comments, setComments] = useState<PublicForumComment[]>([])
  const [interests, setInterests] = useState<PublicForumInterest[]>([])
  const [viewer, setViewer] = useState<User | null>(null)
  const [draft, setDraft] = useState("")
  const [interestDraft, setInterestDraft] = useState("")
  const [editHeadline, setEditHeadline] = useState("")
  const [editBody, setEditBody] = useState("")
  const [editDesiredCount, setEditDesiredCount] = useState("")
  const [editAllowContactRequests, setEditAllowContactRequests] = useState(true)
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
    if (hasDesiredCount && (!Number.isFinite(parsedDesiredCount) || (parsedDesiredCount ?? 0) < 1)) {
      setStatus("Desired beta readers must be a whole number greater than zero.")
      return
    }
    setSavingEdit(true)
    setStatus(null)
    try {
      const updated = await publicApi.updateForumPost(post.id, {
        headline: editHeadline.trim(),
        body: editBody.trim(),
        desiredBetaReaderCount: parsedDesiredCount,
        allowContactRequests: editAllowContactRequests,
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
        headline: post.headline,
        body: post.body,
        desiredBetaReaderCount: post.desired_beta_reader_count,
        allowContactRequests: post.allow_contact_requests,
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
    <div className={`min-h-screen ${isDark ? "bg-[#071019] text-slate-100" : "bg-[#f4efe7] text-slate-950"}`}>
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/public/forum" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>{"<- Back to forum"}</Link>
          {post.author_username ? (
            <Link href={`/public/writers/${post.author_username}` as Route} className={`text-sm ${isDark ? "text-slate-400 hover:text-amber-300" : "text-slate-500 hover:text-amber-700"}`}>
              @{post.author_username}
            </Link>
          ) : null}
        </div>

        <section className={`mt-6 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>{post.genre || post.work_type}</p>
              <h1 className="mt-3 font-serif text-4xl tracking-tight">{post.headline}</h1>
              <p className={`mt-3 text-lg ${isDark ? "text-slate-300" : "text-slate-600"}`}>{post.title}</p>
            </div>
            {isAuthorViewer ? (
              <div className="flex flex-wrap gap-3">
                {canManagePublicAuthoring ? (
                  <button
                    type="button"
                    onClick={() => {
                      setEditing((current) => !current)
                      setStatus(null)
                    }}
                    className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-[#d8c6ab] bg-white text-slate-900 hover:bg-[#f8f1e7]"}`}
                  >
                    {editing ? "Close editor" : "Edit discussion"}
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={savingEdit || (!canManagePublicAuthoring && !isPubliclyInteractive)}
                  onClick={() => void saveDiscussionStatus(isPubliclyInteractive ? "closed" : "open")}
                  className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-300"}`}
                >
                  {savingEdit ? "Saving..." : isPubliclyInteractive ? "Close discussion" : canManagePublicAuthoring ? "Reopen discussion" : "Closed on free plan"}
                </button>
              </div>
            ) : null}
          </div>
          <p className={`mt-5 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{post.body}</p>
          {isAuthorViewer && !canManagePublicAuthoring ? (
            <div className={`mt-5 rounded-3xl border px-5 py-4 text-sm ${isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
              Public discussions require an Author or Architect plan. You can still close this discussion, but editing or reopening it needs a paid author plan.
            </div>
          ) : null}
          {!isPubliclyInteractive ? (
            <div className={`mt-5 rounded-3xl border px-5 py-4 text-sm ${isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
              This discussion is closed. It stays visible to you for review and editing, but new public comments, reactions, and collaborator requests are paused until you reopen it.
            </div>
          ) : null}
          <div className="mt-6 flex flex-wrap gap-3">
            <div className={`rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
              <p className="font-semibold">@{post.author_username || post.author || "writer"}</p>
              <p className={`mt-1 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.author_trust_level} | reputation {formatReputationScore(post.author_reputation_score)}</p>
            </div>
            <div className={`rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
              <p className="font-semibold">{post.comment_count} comments</p>
              <p className={`mt-1 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.interest_count} collaborators asked to connect</p>
            </div>
          </div>
        </section>

        {isAuthorViewer && canManagePublicAuthoring && editing ? (
          <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
            <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Author controls</p>
            <h2 className="mt-2 font-serif text-2xl">Refine this public discussion</h2>
            <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
              Keep the public post focused on the feedback you want. The manuscript itself remains private unless you separately request an approved public sample.
            </p>
            <div className="mt-6 space-y-4">
              <input
                value={editHeadline}
                onChange={(event) => setEditHeadline(event.target.value)}
                placeholder="Headline"
                className={`w-full rounded-3xl border px-5 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
              />
              <textarea
                value={editBody}
                onChange={(event) => setEditBody(event.target.value)}
                placeholder="What kind of beta feedback are you looking for?"
                className={`min-h-[10rem] w-full rounded-3xl border px-5 py-4 text-sm leading-7 outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <input
                  value={editDesiredCount}
                  onChange={(event) => setEditDesiredCount(event.target.value)}
                  placeholder="Desired beta readers"
                  inputMode="numeric"
                  className={`w-full rounded-3xl border px-5 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
                />
                <label className={`flex items-center justify-between rounded-3xl border px-5 py-3 text-sm ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900"}`}>
                  <span>Allow collaborator contact requests</span>
                  <input
                    type="checkbox"
                    checked={editAllowContactRequests}
                    onChange={(event) => setEditAllowContactRequests(event.target.checked)}
                    className="h-4 w-4"
                  />
                </label>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => void saveEdit()}
                  disabled={savingEdit}
                  className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-300"}`}
                >
                  {savingEdit ? "Saving..." : "Save discussion"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditing(false)
                    resetEditorFromPost(post)
                  }}
                  className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-[#d8c6ab] bg-white text-slate-900 hover:bg-[#f8f1e7]"}`}
                >
                  Cancel
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {!isAuthorViewer ? (
          <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Collaborator contact</p>
                <h2 className="mt-2 font-serif text-2xl">Offer to beta read</h2>
              </div>
              <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{viewer ? `Signed in as @${viewer.username || "member"}` : "Sign in to contact this author."}</p>
            </div>
            <div className={`mt-5 rounded-3xl border px-5 py-4 text-sm leading-7 ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-[#eadfce] bg-[#fbf7f0] text-slate-700"}`}>
              This discussion sits in LoreVia&apos;s optional public layer for authors who want outside visibility. The core product still centers on private manuscript work, invited beta readers, and collaborator feedback inside the author workspace.
            </div>
            {post.viewer_interest_status ? (
              <div className={`mt-5 rounded-3xl border px-5 py-4 text-sm ${isDark ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
                You already sent this author a collaborator note. Current status: {post.viewer_interest_status}.
              </div>
            ) : post.allow_contact_requests && isPubliclyInteractive ? (
              <div className="mt-5">
                <textarea
                  value={interestDraft}
                  onChange={(event) => setInterestDraft(event.target.value)}
                  placeholder="Tell the author what genres you read well, what feedback you can provide, and why you'd be a useful beta reader."
                  className={`min-h-[9rem] w-full rounded-3xl border px-5 py-4 text-sm leading-7 outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
                />
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    disabled={interestSubmitting || !interestDraft.trim()}
                    onClick={() => void submitInterest()}
                    className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-300"}`}
                  >
                    {interestSubmitting ? "Sending..." : "Send collaborator note"}
                  </button>
                </div>
              </div>
            ) : (
              <div className={`mt-5 rounded-3xl border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-[#d8c6ab] text-slate-500"}`}>
                {isPubliclyInteractive
                  ? "This author is not taking direct collaborator requests through the public forum right now."
                  : "This discussion is closed, so direct collaborator requests are paused right now."}
              </div>
            )}
          </section>
        ) : null}

        {isAuthorViewer ? (
          <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Incoming collaborators</p>
                <h2 className="mt-2 font-serif text-2xl">Reader interest</h2>
              </div>
              <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{interests.length} contact request{interests.length === 1 ? "" : "s"}</p>
            </div>
            {interestLoadFailed ? (
              <div className={`mt-5 rounded-3xl border px-5 py-4 text-sm ${isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
                Collaborator notes could not be loaded right now. Refresh this page to try again.
              </div>
            ) : interests.length === 0 ? (
              <div className={`mt-5 rounded-3xl border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-[#d8c6ab] text-slate-500"}`}>
                No collaborator notes have arrived for this public discussion yet.
              </div>
            ) : (
              <div className="mt-5 space-y-4">
                {interests.map((interest) => (
                  <article key={interest.id} className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">@{interest.interested_username || interest.interested_email}</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>{interest.interested_email}</p>
                      </div>
                      <div className="text-right">
                        <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>{interest.status}</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{new Date(interest.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                    <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{interest.message}</p>
                  </article>
                ))}
              </div>
            )}
          </section>
        ) : null}

        <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Conversation</p>
              <h2 className="mt-2 font-serif text-2xl">Public comments</h2>
            </div>
            <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{viewer ? `Signed in as @${viewer.username || "member"}` : "Sign in to join the discussion."}</p>
          </div>

          {status ? <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{status}</p> : null}

          {isPubliclyInteractive ? (
            <div className="mt-5">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Add a thoughtful public comment about clarity, pacing, trust, or what you'd want to review."
                className={`min-h-[9rem] w-full rounded-3xl border px-5 py-4 text-sm leading-7 outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={submitting || !draft.trim()}
                  onClick={() => void submitComment()}
                  className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-300"}`}
                >
                  {submitting ? "Posting..." : "Post comment"}
                </button>
              </div>
            </div>
          ) : (
            <div className={`mt-5 rounded-3xl border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-[#d8c6ab] text-slate-500"}`}>
              Public comments are paused while this discussion is closed.
            </div>
          )}

          <div className="mt-8 space-y-4">
            {comments.length === 0 ? (
              <div className={`rounded-3xl border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-[#d8c6ab] text-slate-500"}`}>No public comments are visible on this discussion yet.</div>
            ) : comments.map((comment) => (
              <article key={comment.id} className={`rounded-3xl border px-5 py-5 ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {comment.author_username ? (
                        <Link href={`/public/writers/${comment.author_username}` as Route} className={`font-semibold ${isDark ? "text-white hover:text-amber-300" : "text-slate-900 hover:text-amber-700"}`}>
                          @{comment.author_username}
                        </Link>
                      ) : (
                        <p className="font-semibold">Collaborator</p>
                      )}
                      <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{comment.author_trust_level}</span>
                      <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Rep {formatReputationScore(comment.author_reputation_score)}</span>
                      {comment.can_edit ? <span className={`rounded-full px-2 py-0.5 text-[11px] ${isDark ? "bg-amber-400/15 text-amber-200" : "bg-amber-100 text-amber-800"}`}>You</span> : null}
                    </div>
                    <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{comment.body}</p>
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
                    {isPubliclyInteractive ? (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={reactingId === comment.id}
                          onClick={() => void react(comment, "like")}
                          className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${comment.reaction === "like" ? (isDark ? "border-emerald-400/60 bg-emerald-400/15 text-emerald-200" : "border-emerald-300 bg-emerald-50 text-emerald-700") : (isDark ? "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10" : "border-white bg-white text-slate-600 hover:border-slate-300")}`}
                        >
                          Like {comment.like_count}
                        </button>
                        <button
                          type="button"
                          disabled={reactingId === comment.id}
                          onClick={() => void react(comment, "dislike")}
                          className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${comment.reaction === "dislike" ? (isDark ? "border-rose-400/60 bg-rose-400/15 text-rose-200" : "border-rose-300 bg-rose-50 text-rose-700") : (isDark ? "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10" : "border-white bg-white text-slate-600 hover:border-slate-300")}`}
                        >
                          Dislike {comment.dislike_count}
                        </button>
                      </div>
                    ) : (
                      <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Reactions paused</p>
                    )}
                    <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{new Date(comment.created_at).toLocaleString()}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
