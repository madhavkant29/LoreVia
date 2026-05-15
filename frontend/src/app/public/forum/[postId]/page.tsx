"use client"

import Link from "next/link"
import type { Route } from "next"
import { useEffect, useState } from "react"
import { useParams } from "next/navigation"

import { authApi } from "@/lib/api/auth"
import { publicApi } from "@/lib/api/public"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore } from "@/lib/utils/publicForum"
import type { PublicForumComment, PublicForumPost } from "@/types/public"
import type { User } from "@/types/user"

export default function PublicForumPostPage() {
  const { postId } = useParams<{ postId: string }>()
  const [post, setPost] = useState<PublicForumPost | null>(null)
  const [comments, setComments] = useState<PublicForumComment[]>([])
  const [viewer, setViewer] = useState<User | null>(null)
  const [draft, setDraft] = useState("")
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [reactingId, setReactingId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    let active = true
    setLoading(true)
    setStatus(null)
    Promise.all([
      publicApi.getForumPost(postId),
      publicApi.listForumComments(postId),
      authApi.me().catch(() => null),
    ]).then(([postPayload, commentsPayload, viewerPayload]) => {
      if (!active) return
      setPost(postPayload)
      setComments(commentsPayload)
      setViewer(viewerPayload)
    }).catch(() => {
      if (!active) return
      setStatus("Could not load this public discussion.")
    }).finally(() => {
      if (!active) return
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [postId])

  const refreshComments = async () => {
    const items = await publicApi.listForumComments(postId)
    setComments(items)
    setPost((current) => current ? { ...current, comment_count: items.length } : current)
  }

  const submitComment = async () => {
    if (!viewer) {
      setStatus("Sign in to leave a public forum comment.")
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
          <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>{post.genre || post.work_type}</p>
          <h1 className="mt-3 font-serif text-4xl tracking-tight">{post.headline}</h1>
          <p className={`mt-3 text-lg ${isDark ? "text-slate-300" : "text-slate-600"}`}>{post.title}</p>
          <p className={`mt-5 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{post.body}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <div className={`rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
              <p className="font-semibold">@{post.author_username || post.author || "writer"}</p>
              <p className={`mt-1 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.author_trust_level} | reputation {formatReputationScore(post.author_reputation_score)}</p>
            </div>
            <div className={`rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
              <p className="font-semibold">{post.comment_count} comments</p>
              <p className={`mt-1 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.interest_count} readers asked to connect</p>
            </div>
          </div>
        </section>

        <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Conversation</p>
              <h2 className="mt-2 font-serif text-2xl">Reader comments</h2>
            </div>
            <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{viewer ? `Signed in as @${viewer.username || "member"}` : "Read-only until you sign in."}</p>
          </div>

          <div className="mt-5">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Add a thoughtful comment about clarity, pacing, trust, or what you'd want to review."
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
              {status ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{status}</p> : null}
            </div>
          </div>

          <div className="mt-8 space-y-4">
            {comments.length === 0 ? (
              <div className={`rounded-3xl border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-[#d8c6ab] text-slate-500"}`}>No comments yet. Be the first reader to set the tone.</div>
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
                        <p className="font-semibold">Reader</p>
                      )}
                      <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{comment.author_trust_level}</span>
                      <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Rep {formatReputationScore(comment.author_reputation_score)}</span>
                      {comment.can_edit ? <span className={`rounded-full px-2 py-0.5 text-[11px] ${isDark ? "bg-amber-400/15 text-amber-200" : "bg-amber-100 text-amber-800"}`}>You</span> : null}
                    </div>
                    <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{comment.body}</p>
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
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
