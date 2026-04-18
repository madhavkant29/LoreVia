 "use client"
import Link from "next/link"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { theme, toggleTheme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div
      className={`min-h-[100dvh] px-4 py-8 transition-colors ${
        isDark
          ? "bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.18),transparent_22%),radial-gradient(circle_at_88%_10%,rgba(56,189,248,0.14),transparent_26%),linear-gradient(180deg,#06101f_0%,#09162a_52%,#0d1d38_100%)] text-slate-100"
          : "bg-[radial-gradient(circle_at_top_left,#efe3c8,transparent_22%),radial-gradient(circle_at_88%_10%,#dde9fb,transparent_26%),linear-gradient(180deg,#f7f3ec_0%,#f7f7f5_52%,#eef2f8_100%)] text-stone-950"
      }`}
    >
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-5xl flex-col justify-between gap-10">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className={`flex items-center gap-3 ${isDark ? "text-white" : "text-stone-900"}`}>
            <div className={`flex h-11 w-11 items-center justify-center rounded-2xl text-sm font-semibold ${
              isDark ? "bg-white/10 text-white border border-white/10" : "bg-stone-950 text-white"
            }`}>LV</div>
            <div>
              <p className="font-serif text-2xl tracking-tight">LoreVia</p>
              <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>Never lose the thread</p>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-300 bg-white/80 text-stone-700 hover:bg-white"
              }`}
            >
              {isDark ? "Light mode" : "Dark mode"}
            </button>
            <Link
              href="/"
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-300 bg-white/80 text-stone-700 hover:bg-white"
              }`}
            >
              Back to home
            </Link>
          </div>
        </header>

        <div className="grid gap-8 lg:grid-cols-[0.95fr_0.7fr] lg:items-center">
          <section className="hidden lg:block">
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-300" : "text-amber-700"}`}>Read with continuity</p>
            <h1 className={`mt-4 max-w-xl font-serif text-5xl leading-[1.05] ${isDark ? "text-white" : "text-stone-950"}`}>
              Stay inside the story,
              <br />
              not inside the friction.
            </h1>
            <p className={`mt-5 max-w-xl text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              LoreVia keeps context, characters, and narrative threads close at hand so dense books feel navigable without flattening them into generic chat.
            </p>
            <div className="mt-8 grid max-w-xl gap-4 sm:grid-cols-2">
              {[
                ["Spoiler-safe by design", "Summaries and context stay tied to what you have already read."],
                ["Character continuity", "Aliases, motives, and relationships are gathered into one evolving view."],
                ["Built for real books", "Long fiction, classics, and series stay readable without losing the thread."],
                ["Grounded reading tools", "Search, graph, timeline, and recall stay anchored to the text."],
              ].map(([title, body]) => (
                <div key={title} className={`rounded-[1.6rem] border p-4 shadow-[0_18px_55px_-45px_rgba(15,23,42,0.28)] ${
                  isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/70"
                }`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{body}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="mx-auto w-full max-w-md">{children}</div>
        </div>

        <footer className={`flex flex-wrap items-center justify-center gap-4 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          <Link href="/terms" className={isDark ? "hover:text-white" : "hover:text-stone-900"}>Terms &amp; Conditions</Link>
          <Link href="/compliance" className={isDark ? "hover:text-white" : "hover:text-stone-900"}>Compliance</Link>
          <Link href="/eula" className={isDark ? "hover:text-white" : "hover:text-stone-900"}>EULA</Link>
          <Link href="/contact" className={isDark ? "hover:text-white" : "hover:text-stone-900"}>Contact</Link>
        </footer>
      </div>
    </div>
  )
}
